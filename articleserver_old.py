__author__ = 'Adam'
import os.path
import flask
import psycopg2
from contextlib import contextmanager

app = flask.Flask(__name__)
app.config.from_pyfile('settings.py')
if os.path.exists('localsettings.py'):
    app.config.from_pyfile('localsettings.py')


@contextmanager
def db_cursor():
    # Get the database connection from the configuration
    dbc = psycopg2.connect(**app.config['PG_ARGS'])
    try:
        cur = dbc.cursor()
        try:
            yield cur
        finally:
            cur.close()
    finally:
        dbc.close()


@app.route('/')
def home_page():
    with db_cursor() as cur:
        cur.execute('SELECT COUNT(article_id) FROM article')
        row = cur.fetchone()
        print(row)
        paper_count = row[0]
        cur.execute('SELECT COUNT(pub_id) FROM publication')
        pub_count = cur.fetchone()[0]

    return flask.render_template('home.html',
                                 paper_count=paper_count,
                                 pub_count=pub_count)


@app.route('/publications/')
def pub_list():
    with db_cursor() as cur:
        cur.execute('SELECT pub_id, pub_title, COUNT(issue_id)'
                    ' FROM publication JOIN issue USING (pub_id)'
                    ' GROUP BY pub_id, pub_title')
        publications = []
        for id, title, issues in cur:
            publications.append({'id': id, 'title': title,
                                 'issue_count': issues})

    return flask.render_template('publist.html',
                                 publications=publications)


@app.route('/publications/<int:pub_id>')
def pub_info(pub_id):
    with db_cursor() as cur:
        cur.execute('SELECT pub_id, pub_title, COUNT(issue_id)'
                    ' FROM publication'
                    ' JOIN issue USING (pub_id)'
                    ' WHERE pub_id = %s'
                    ' GROUP BY pub_id, pub_title',
                    (pub_id,))
        row = cur.fetchone()
        if row is None:
            flask.abort(404)

        # we have a row, unpack it
        id, title, issues = row
        pub = {'id': id, 'title': title,
               'issue_count': issues}

        cur.execute('''
          SELECT issue_id, iss_volume, iss_number, iss_title,
            iss_date,
            EXTRACT(year from iss_date) AS iss_year
          FROM issue
          WHERE pub_id = %s
          ORDER BY iss_date
        ''', (pub_id,))
        # this syntax builds a new list using an embedded for loop
        # it is called a 'list comprehension'
        issues = [{'id': id, 'volume': vol, 'number': num, 'title': title,
                   'date': date, 'year': int(year)}
                  for (id, vol, num, title, date, year) in cur]

    return flask.render_template('pubinfo.html',
                                 pub=pub, issues=issues)


@app.route('/publications/<int:pub_id>/issues/<int:iss_id>')
def issue(pub_id, iss_id):
    # we will ignore pub_id
    with db_cursor() as cur:
        cur.execute('''
            SELECT pub_id, pub_title, iss_volume, iss_number, iss_title, iss_date
            FROM issue JOIN publication USING (pub_id)
            WHERE issue_id = %s
        ''', (iss_id,))
        row = cur.fetchone()
        if row is None:
            flask.abort(404)

        pub_id, pub_title, iss_vol, iss_num, iss_title, iss_date = row
        pub = {'id': pub_id, 'title': pub_title}
        issue = {'volume': iss_vol,
                 'number': iss_num,
                 'title': iss_title,
                 'date': iss_date}

        cur.execute('''
            SELECT article_id, title
            FROM article
            WHERE issue_id = %s
        ''', (iss_id,))
        articles = []
        for aid, title in cur:
            articles.append({'id': aid, 'title': title})

    return flask.render_template('issue.html', pub=pub, issue=issue,
                                 articles=articles)


@app.route('/articles/<int:aid>')
def article(aid):
    with db_cursor() as cur:
        cur.execute('SELECT article_id, title, abstract,'
                    '       iss_date, iss_number, iss_volume, pub_title'
                    ' FROM article'
                    ' JOIN issue USING (issue_id)'
                    ' JOIN publication USING (pub_id)'
                    ' WHERE article_id = %s', (aid,))
        row = cur.fetchone()
        if row is None:
            flask.abort(404)

        id, title, abstract, iss_date, iss_num, iss_vol, pub_title = row
        paper = {'id': id,
                 'title': title,
                 'abstract': abstract,
                 'issue': {
                     'date': iss_date,
                     'number': iss_num,
                     'volume': iss_vol,
                     'pub_title': pub_title
                 }}

        cur.execute('SELECT author_name'
                    ' FROM article_author'
                    ' JOIN author USING (author_id)'
                    ' WHERE article_id = %s'
                    ' ORDER BY position', (aid,))
        authors = []
        for name, in cur:
            authors.append(name)
        paper['authors'] = authors

    return flask.render_template('article.html',
                                 paper=paper)


if __name__ == '__main__':
    app.run()