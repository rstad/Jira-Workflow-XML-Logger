========================
Jira Workflow XML Logger
========================

Example / Demo
--------------

I started up a Jira trial locally, made some config changes over the course of a few days, and pointed this script at it periodically.  The results can be found here: `https://github.com/rstad/jira-workflow-log-example <https://github.com/rstad/jira-workflow-log-example>`_

Requirements
------------

- Python 3.6+
- credentials for a user that has sufficient privileges to retrieve workflows from Jira
- a repo you can access for committing changes to

I've only tested this against Server/DC, no idea if it would have any use with Cloud.

Usage
-----

For now I'm just running this as a cron job but I'm sure you could adapt it for other use.

Manual steps:

#. ``git clone`` this repo and ``cd`` into the directory.
#. ``cp .env.example .env``
#. edit ``.env`` to have the appropriate values
#. ``python3 -m venv env``
#. ``source env/bin/activate``
#. ``pip install -r requirements.txt``
#. ``python workflowlog.py``


------------

::

 ❯ python workflowlog.py -h
 usage: workflowlog.py [-h] [--firstrun] [--nocleanup]
 
 Script to capture changes to workflows in Jira
 
 optional arguments:
   -h, --help   show this help message and exit
   --firstrun   Gets ALL workflows and attempts to make initial commit to an empty repo
   --nocleanup  prevents deleting work dir after run

------------

Background
----------

The idea for this script came up when I was talking to somebody about how we could better track who made changes to a workflow, and what changes they had made.

The actions we resolved to take from that meeting were to essentially ask people to remember to save backup copies of workflows when publishing updates.  This sounded to me like a good opportunity to automate.

Approach
--------
It's possible to get a list of all the workflows that Jira has, in a giant JSON blob.  It was not immediately obvious to me how to tell which ones are active or inactive, but for the purposes of simply logging changes to workflows, that doesn't matter too much.

What the big list has that we do care about is:

#. a ``lastModifiedDate``
#. a ``lastModifiedUser``
#. a uniquely identifying ``name``

With this, the next question is, how do I get the workflow as an XML file, for the purposes of storing and performing ``diff`` against later?

It `turns out <https://community.atlassian.com/t5/Answers-Developer-Questions/How-to-get-all-workflow-steps-through-rest-api/qaq-p/542091>`_ that this is pretty straightforward by performing the appropriate series of requests to get authenticated, and then simply trying to download it by name using:

``$JIRA_URL/secure/admin/workflows/ViewWorkflowXml.jspa?workflowMode=live&workflowName=My+Workflow+Name``

So far, we've now got a list of every workflow, the XML for that workflow, who last modified that workflow (which is also in the XML), and when the workflow was last updated.

To put it all together, we use this script which will:

#. Retrieve a list of all workflows
#. Check for those that were last updated recently (e.g. since the last time the script was run)
#. For each workflow identified, download the XML
#. Add to a git repo and commit the changes

