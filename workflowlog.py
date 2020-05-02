import os # to read environment variables and deal with directory stuff
import sys # for sys.exit only?
import argparse # for taking arguments
import httpx # to make http requests to JIRA and Slack
import json # for working with responses from Jira, etc.
import untangle # to pull out specific data from the workflow xmls
import parsedatetime # for parsing relative and human readable time descriptions
from git import Repo,Git # for git operations
from shutil import rmtree # for deleting work dir
from urllib.parse import quote_plus # converting workflow names to URL properly
from datetime import datetime,timedelta # working with dates and comparing them
from dotenv import load_dotenv # to set environment variables, mainly
load_dotenv()

parser = argparse.ArgumentParser(description="Script to capture changes to workflows in Jira")
parser.add_argument('--firstrun',help="Gets ALL workflows and attempts to make initial commit",action='store_true')
parser.add_argument('--nocleanup',help="prevents deleting work dir after run",action='store_true')
args = parser.parse_args()

git_ssh_command = 'ssh -i %s' % os.getenv("gitkeypath")

def setupWorkdir():
    if os.path.isdir("./work"):
        rmtree("./work")
    if (args.firstrun):
        os.makedirs("work")
        repo = Repo.init("./work",env={"GIT_SSH_COMMAND":git_ssh_command})
    else:
        repo = Repo.clone_from(os.getenv("gitremote"),"./work",depth=1,env={"GIT_SSH_COMMAND":git_ssh_command})
    return repo

def commitChanges(repo):
    repo.git.add(".")
    changedFiles = repo.git.diff("HEAD", name_only=True).splitlines()
    commitMessage = "Updated Workflow Count: "+str(len(changedFiles))+"\n\n"
    for f in changedFiles:
        o = untangle.parse("./work/"+f)
        commitMessage += '"'+f[:-4]+'"'+" by "+o.workflow.meta[1].cdata+"\n"
    if (args.firstrun):
        repo.index.commit("initial commit")
        origin = repo.create_remote('origin',os.getenv("gitremote"))
        repo.create_head('master')
        origin.push('master',env={"GIT_SSH_COMMAND":git_ssh_command})
    elif (len(repo.index.diff("HEAD"))>0): # there exists changes
        repo.index.commit(commitMessage)
        origin = repo.remote('origin')
        origin.push()

def cleanup():
    if (args.nocleanup):
        return
    rmtree("./work")

def getWorkflows():
    jira_url_base = os.getenv("jirabaseurl")
    jira_auth_user = os.getenv("jirauser")
    jira_auth_password = os.getenv("jirapass")
    workflows=[]
    with httpx.Client(auth=(jira_auth_user,jira_auth_password)) as jiraclient:
        workflowList = jiraclient.get(jira_url_base + 'rest/api/2/workflow',timeout=10.0)
        workflows = json.loads(workflowList.text)

    updated_workflows = []
    current_time = datetime.now()
    timeparser = parsedatetime.Calendar()
    # this is super gross, and is largely avoided if you use the jira config property to disable relativized dates
    for wf in workflows:
        modified_datetime = datetime.now()
        if (args.firstrun):
            updated_workflows.append(wf['name'])
            continue
        elif (wf['default']):
            # there is only one default workflow, and it is read only
            continue
        elif ("lastModifiedDate" not in wf):
            # going to skip workflows that have never been modified
            continue
        elif ("now" in wf['lastModifiedDate']): # the "Just now" case
            modified_datetime = datetime.now()-timedelta(minutes=1)
        elif ("ago" in wf['lastModifiedDate']): # the "X minutes ago" and "Y hours ago" cases
            if ("minute" in wf['lastModifiedDate']):
                timestruct,status = timeparser.parse(wf['lastModifiedDate'])
                modified_datetime = datetime(*timestruct[:6])
            elif ("hour" in wf['lastModifiedDate']):
                timestruct,status = timeparser.parse(wf['lastModifiedDate'])
                modified_datetime = datetime(*timestruct[:6])
        elif ("Yesterday" in wf['lastModifiedDate']): # Yesterday H:MM PM case
            timestruct,status = timeparser.parse(wf['lastModifiedDate'])
            modified_datetime = datetime(*timestruct[:6])
        else:
            modified_datetime = datetime.strptime(wf['lastModifiedDate'], '%d/%b/%y %I:%M %p')
        delta = current_time - modified_datetime
        if (delta.days < 1):
            updated_workflows.append(wf['name'])

    jiraheaders = {"X-Atlassian-Token" : "no-check"}
    with httpx.Client(auth=(jira_auth_user,jira_auth_password),headers=jiraheaders) as jirasudoclient:
        myself = jirasudoclient.get(jira_url_base + 'rest/api/2/myself')
        websudo_headers = {"content-type":"application/x-www-form-urlencoded"}
        for wf in updated_workflows:
            websudo_data = {'webSudoPassword':jira_auth_password,'webSudoDestination':"/secure/admin/workflows/ViewWorkflowXml.jspa?workflowMode=live&workflowName="+quote_plus(wf)}
            websudo = jirasudoclient.post(jira_url_base + 'secure/admin/WebSudoAuthenticate.jspa',headers=websudo_headers,data=websudo_data)
            with open("./work/"+wf.replace("/","_")+".xml",'w') as file:
                file.write(websudo.text)

if __name__ == '__main__':
    try:
        repo = setupWorkdir()
        getWorkflows()
        commitChanges(repo)
        cleanup()
    except KeyboardInterrupt:
        print('keyboard interrupt')
