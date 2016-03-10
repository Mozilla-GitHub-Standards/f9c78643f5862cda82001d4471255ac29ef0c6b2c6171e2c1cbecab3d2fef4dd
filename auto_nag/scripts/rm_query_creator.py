#!/usr/bin/python

import requests
import re
import datetime
import subprocess
import os
import json
from argparse import ArgumentParser
from auto_nag.bugzilla.utils import get_config_path, get_project_root_path


def getTemplateValue(url):
    version_regex = re.compile(".*<p>(.*)</p>.*")
    template_page = str(requests.get(url).text.encode('utf-8')).replace('\n', '')
    parsed_template = version_regex.match(template_page)
    return parsed_template.groups()[0]


release_version = getTemplateValue("https://wiki.mozilla.org/Template:RELEASE_VERSION")
beta_version = getTemplateValue("https://wiki.mozilla.org/Template:BETA_VERSION")
aurora_version = getTemplateValue("https://wiki.mozilla.org/Template:AURORA_VERSION")
central_version = getTemplateValue("https://wiki.mozilla.org/Template:CENTRAL_VERSION")

fixed_without_uplifts_url = "https://bugzilla.mozilla.org/buglist.cgi?v4=affected&o5=equals&f1=cf_status_firefox" + central_version + "&o3=equals&v3=affected&o1=equals&j2=OR&resolution=---&resolution=FIXED&f4=cf_status_firefox" + beta_version + "&v5=affected&query_format=advanced&f3=cf_status_firefox" + aurora_version + "&f2=OP&o4=equals&f5=cf_status_firefox" + release_version + "&v1=fixed&f7=CP"

# TODO - sort the queries according to a priority flag
# TODO - separate queries for sec bugs, for now hide summary
# TODO - fix the 'untouched' queries

urls = [
    (5, ["Notify release managers when bugs are marked fixed in nightly but still affected for aurora, beta or release", "fixed_without_uplifts", fixed_without_uplifts_url, 0])
]


def createQuery(queries_dir, title, short_title, url, show_summary):
    file_name = queries_dir + str(datetime.date.today()) + '_' + short_title
    if not os.path.exists(queries_dir):
        os.makedirs(queries_dir)
    qf = open(file_name, 'w')
    qf.write("query_name = \'" + title + "\'\n")
    qf.write("query_url = \'" + url + "\'\n")
    qf.write("show_summary = \'" + str(show_summary) + "\'\n")
    return file_name


def createQueriesList(queries_dir, weekday, print_all):
    queries = []
    for url in urls:
        if weekday >= 0 and weekday < 5 and url[0] == 5:
            queries.append(createQuery(queries_dir, title=url[1][0], short_title=url[1][1], url=url[1][2], show_summary=url[1][3]))
        if weekday == 0 and url[0] == 0:
            queries.append(createQuery(queries_dir, title=url[1][0], short_title=url[1][1], url=url[1][2], show_summary=url[1][3]))
        if weekday == 3 and url[0] == 3:
            queries.append(createQuery(queries_dir, title=url[1][0], short_title=url[1][1], url=url[1][2], show_summary=url[1][3]))
    print queries
    return queries


def cleanUp(queries_dir):
    try:
        for file in os.listdir(queries_dir):
            if file.startswith(str(datetime.date.today())):
                os.remove(os.path.join(queries_dir, file))
        return True
    except Exception as error:
        print "Error: ", str(error)
        return False

if __name__ == '__main__':
    # basic setups
    CONFIG_JSON = get_config_path()
    config = json.load(open(CONFIG_JSON, 'r'))
    scripts_dir = get_project_root_path() + "auto_nag/scripts/"
    queries_dir = get_project_root_path() + "queries/"

    parser = ArgumentParser(__doc__)
    parser.set_defaults(
        queries_only=False,
    )
    parser.add_argument("-q", "--queries-only", dest="queries_only", action="store_true",
                        help="just create and print queries")

    options, args = parser.parse_known_args()
    weekday = datetime.datetime.today().weekday()
    queries = createQueriesList(queries_dir, weekday, print_all=options.queries_only)
    if options.queries_only:
        for url in urls:
            print url
    else:
        command = [
            scripts_dir + "email_nag.py",
            "-t", "daily_email",
            "--no-verification",
            "-m", config['ldap_username'],
            "-p", config['ldap_password'],
            "-b", config['bz_api_key'],
            "-c",
            "-e", "release-mgmt@mozilla.com"]
        for query in queries:
            command.append('-q')
            command.append(query)
        subject = datetime.datetime.today().strftime("%A %b %d") + " -- Fixed in %s, Affecting %s, %s or %s" % (central_version, aurora_version, beta_version, release_version)
        command.extend(['-s',  subject])
        # send all other args to email_nag script argparser
        command.extend(args)
        subprocess.call(command)
        cleanUp(queries_dir)