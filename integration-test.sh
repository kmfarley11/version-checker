#!/bin/bash
#
# integration-test.sh
#
#   Bash script to excercise the version checker utility against a live repo
#   Expects a virtual environment to be available (python3 -m venv .venv)
#   DISCLAIMER: Will replace pre-push if exists with version checker
#
#   Usage:
#       bash integration-test.sh
#       bash integration-test.sh my_custom_venv/
#
VENV=${1:-.venv}
. ${VENV}/bin/activate

# some verification first (python, venv, git)
if [ ! "$?" -eq "0"  ] ; then
    echo "Error! virtual env ${VENV} not available"
    exit 1
fi

git status
if [ ! "$?" -eq "0"  ] ; then
    echo "Error! invalid git repo detected, must be run in a git repo..."
    exit 1
fi

if [ ! -z $(git diff --name-only) ] ; then
    echo "Error! unstaged changes detected, stash or reset to continue"
    exit 1
fi

echo "TEST SETUP"
echo "Replacing whatever is in .git/hooks/pre-push with version checker"
rm .git/hooks/pre-push
version_checker -i pre-push || exit 1
PREVBRANCH=$(git branch | grep -oE '\*.*' | grep -oE '[a-Z0-9]+')
NUBRANCH=$(python -c "import uuid; print(uuid.uuid4())")
BASEBRANCH=origin/master

echo "Creating temporary branch for testing... '$NUBRANCH'"
echo "switching away from ${PREVBRANCH}, basing off $BASEBRANCH"
git checkout ${BASEBRANCH}
git checkout -b ${NUBRANCH}

echo "TEST START"
echo "TEST STEP: new branch needs version change"
version_checker && exit 1

echo "TEST STEP: verify pre-push fails as well"
touch testfile
git add testfile && git commit -m "testcommit" || exit 1
git push origin ${NUBRANCH} --dry-run && exit 1
git reset --hard HEAD~1 || exit 1

echo "TEST STEP: update versions"
bump2version patch --commit || exit 1

echo "TEST STEP: manually verify all files changed..."
cat .bumpversion.cfg | grep -oE 'file:.*[^]]' | grep -oE '[^file:].*' | sort > expected.lst
git diff ${PREVBRANCH}..HEAD --name-only | grep -v .bumpversion.cfg | sort > actual.lst
diff expected.lst actual.lst || exit 1
rm expected.lst actual.lst

echo "TEST STEP: version changes detected & ok now"
version_checker || exit 1
git push origin ${NUBRANCH} --dry-run || exit 1
echo "TEST FINISH"

echo "TEST CLEANUP"
git checkout ${PREVBRANCH} || exit 1
git branch -D ${NUBRANCH} || exit 1

echo "Done. everything seems ok"

