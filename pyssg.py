import os
import re
import json
import errno
import fnmatch
import shutil

# from datetime import datetime

try:
    from urllib.request import pathname2url, url2pathname
except ImportError:
    from urllib import pathname2url, url2pathname

from markdown import markdown
from mako.lookup import TemplateLookup


PAGE_ENCODING = 'UTF-8'

mylookup = TemplateLookup(directories=['./_templates'])

def render_template(templatename, **kwargs):
    mytemplate = mylookup.get_template(templatename)
    return mytemplate.render(**kwargs)


def find_files(pattern, root):
    for path, dirs, files in os.walk(root):
        for f in files:
            if fnmatch.fnmatch(f, pattern):
                yield os.path.join(path, f)


def makedirs(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass


def path2url(path):
    m = re.match(r'(.*)[/\\]index.html?$', path)
    if m:
        path = m.group(1) + os.path.sep
    return pathname2url(os.path.sep + path)


def url2path(url):
    if url.endswith('/'):
        url += 'index.html'
    return url2pathname(url).lstrip(os.path.sep)


class DictDot(dict):
    def __init__(self, arg=None):
        dict.__init__(self, arg)

    def __setattr__(self, key, value):
        self[key] = value

    def __getattr__(self, name):
        return self[name]


def new_dict_dot(data):
    for k, v in data.items():
        if isinstance(v, dict):
            data[k] = new_dict_dot(v)
    return DictDot(data)


def load_config(filepath):
    return new_dict_dot(json.load(open(filepath)))


def read_file(filename):
    with open(filename, 'rb') as fd:
        if fd.read(3) != b'---':
            return None
        lines = []
        offset = 1
        while True:
            line = fd.readline()
            if re.match(b'^---\r?\n', line):
                break
            elif re.match(b'\r?\n', line):
                continue
            elif line == b'':
                return None
            lines.append(line.strip())
            offset += 1
        front_matter = dict()
        for line in lines:
            k, v = line.split(':')
            front_matter[k.lower()] = v.lower()
        page = new_dict_dot(front_matter)
        if not page:
            page = {}
        content = fd.read().decode(PAGE_ENCODING)
        page.content = content.strip()
        return page

def markdown_compiler(content):
    return markdown(content)

# Compilers
suffixes = {
    '.txt': markdown,
    '.md': markdown,
    '.mkd': markdown,
    '.markdown': markdown,
}

def load_pages(path):
    pages = []
    files = list(find_files('*.*', path))
    prefix = os.path.commonprefix(files)

    for f in files:
        name, ext = os.path.splitext(f)

        if not ext in suffixes:
            continue

        page = read_file(f)
        page.content = suffixes[ext](page.content)
        page.url = path2url('{0}.html'.format(os.path.relpath(name, prefix)))
        pages.append(page)

    return pages


def load_posts(path):
    posts = []
    files = list(find_files('*.*', path))
    # prefix = os.path.commonprefix(files)

    for f in files:
        post_re = re.compile('(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})-(?P<title>.+)')

        name, ext = os.path.splitext(f)
        if not ext in suffixes:
            continue

        m = post_re.match(os.path.basename(name))
        if not m:
            continue

        post = read_file(f)
        post.content = suffixes[ext](post.content)
        # date_str = '{year}-{month}-{day}'.format(**m.groupdict())
        # post.date = datetime.strptime(date_str, '%Y-%m-%d')
        post.date = '{year}-{month}-{day}'.format(**m.groupdict())
        # post.id = '/{year}/{month}/{day}/{title}'.format(**m.groupdict())
        post.permanlink = path2url('{year}/{month}/{day}/{title}.html'.format(**m.groupdict()))
        post.previous = None
        post.next = None
        post.tags = [t.strip() for t in post.tags.split(',')] if not post.get('tags', None) is None else []
        posts.append(post)

    posts.sort(key=lambda post: post.date, reverse=True)
    n = len(posts)
    for i, post in enumerate(posts):
        if i < n - 1:
            post.next = posts[i + 1]
        if i > 0:
            post.previous = posts[i - 1]
    return posts


def new_site(config):
    return DictDot(config)


def load_site(site_info):
    site = new_site(site_info)
    site.pages = load_pages('_pages')
    site.posts = load_posts('_posts')
    return site


def build_site(site, config):
    # stylesheets
    try:
        shutil.copytree('_static', config.output)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass

    # Build pages
    if site.pages:
        pages_path = os.path.join(config.output, 'pages')
        for page in site.pages:
            fname = os.path.join(pages_path, url2path(page.url))
            makedirs(os.path.dirname(fname))
            f = open(fname, 'w+')
            f.write(render_template('page.html', site=site, page=page))
            f.close()
            # pass

    # Build posts
    if site.posts:
        posts_path = os.path.join(config.output, 'posts')
        for post in site.posts:
            fname = os.path.join(posts_path, url2path(post.permanlink))
            makedirs(os.path.dirname(fname))
            f = open(fname, 'w+')
            f.write(render_template('post.html', site=site, post=post))
            f.close()
            # pass

    f = open(os.path.join(config.output, 'index.html'), 'w+')
    f.write(render_template('index.html', site=site))
    f.close()


def pyssg(basepath):
    config = load_config(os.path.join(basepath, 'config.json'))
    site = load_site(config.site_info)
    build_site(site, config)


def main():
    pyssg(os.getcwd())


if __name__ == '__main__':
    main()