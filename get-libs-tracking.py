from datetime import datetime, date, timedelta
import requests, json, os

BASE = 'https://api.github.com'
ISSUES = '/repos/rust-lang/rust/issues'
EVENTS = '/repos/rust-lang/rust/issues/%s/events'

def get_links(rsp):
    links = {}
    if 'Link' not in rsp.headers:
        return links
    for link in rsp.headers['Link'].split(','):
        url, name = link.split(';')
        parts = name.split('"')
        links[parts[1]] = url[1:-1]
    return links

def collect(url):
    rsp = requests.get(url)
    if rsp.status_code != 200:
        raise Exception((url, rsp.status_code, rsp.json()))
    all = rsp.json()
    links = get_links(rsp)
    while 'next' in links:
        rsp = requests.get(links['next'])
        if rsp.status_code != 200:
            raise Exception((url, rsp.status_code, rsp.json()))
        all += rsp.json()
        links = get_links(rsp)
    return all

def cached(url, fn):
    if os.path.exists(fn):
        with open(fn) as f:
            data = json.load(f)
    else:
        data = collect(url)
        with open(fn, 'w') as f:
            json.dump(data, f, 2)
    return data

def get_issues():
    url = BASE + ISSUES + '?state=all&labels=T-libs,B-unstable'
    return cached(url, 'issues.json')

def get_events(issue):
    return cached(BASE + EVENTS % issue, '%s-events.json' % issue)

def median(ls):
    ls.sort()
    if len(ls) % 2:
        return ls[(len(ls) + 1) // 2]
    else:
        return ls[len(ls) // 2]

def main():
    types = set()
    dates = {}
    created = {}
    for idata in sorted(get_issues(), key=lambda x: x['number']):

        issue = idata['number']
        created[issue] = datetime.strptime(idata['created_at'], '%Y-%m-%dT%H:%M:%SZ') 
        data = []
        state = set()
        updated, closed = None, None
        for ev in get_events(issue):
            dt = datetime.strptime(ev['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            types.add(ev['event'])
            if ev['event'] not in {'labeled', 'unlabeled', 'closed', 'reopened'}:
                continue
            if ev['event'] in {'labeled', 'unlabeled'}:
                if ev['label']['name'] not in {'T-libs', 'B-unstable'}:
                    continue
                data.append((dt, ev['event'], ev['label']['name']))
                if ev['event'] == 'labeled':
                    state.add(ev['label']['name'])
                    if len(state) == 2:
                        dates.setdefault(dt.date(), (set(), set()))[0].add(issue)
                else:
                    if len(state) == 2:
                        dates.setdefault(dt.date(), (set(), set()))[1].add(issue)
                    state.remove(ev['label']['name'])
            elif ev['event'] == 'reopened':
                dates.setdefault(dt.date(), (set(), set()))[0].add(issue)
                data.append((dt, 'reopened'))
                closed = None
            else:
                dates.setdefault(dt.date(), (set(), set()))[1].add(issue)
                data.append((dt, 'closed'))
                closed = dt

    cur = [min(dates), set()]
    while cur[0] < date.today():
        if cur[0] in dates:
            cur[1] = (cur[1] | dates[cur[0]][0]) - dates[cur[0]][1]
        print(cur[0], len(cur[1]), (cur[0] - median([created[i] for i in cur[1]]).date()).days)
        cur[0] += timedelta(1)

if __name__ == '__main__':
    main()
