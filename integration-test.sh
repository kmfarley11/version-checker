#!/bin/bash
#
# integration-test.sh
#
#   Bash script to excercise the version checker utility against a live repo
#   Expects python3.11+
#   DISCLAIMER: Will replace pre-push if exists with version checker
#
#   Usage:
#       bash integration-test.sh
#       bash integration-test.sh .venv/bin/python
#
PY=${1:-python}
${PY} --version | grep -E '3\.(11|12|13|14)'

# need to have references for origin/main or master etc. for this to work...
git fetch

# some verification first (python, venv, git)
if [ ! "$?" -eq "0"  ] ; then
    echo "Error! python version ${PY} too old, try with a newer one"
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
PREVBRANCH=$(git branch | grep -oE '\*.*' | grep -oE '[A-Za-z0-9\-]+')
NUBRANCH=$(${PY} -c "import uuid; print(uuid.uuid4())")
NUNUBRANCH=$(${PY} -c "import uuid; print(uuid.uuid4())")
BASEBRANCH=origin/main

echo "Creating temporary branch for testing... '$NUBRANCH'"
echo "switching away from ${PREVBRANCH}, basing off $BASEBRANCH"
git checkout ${BASEBRANCH}
git checkout -b ${NUBRANCH}

echo "TEST START"
echo "TEST STEP: new branch with new commit needs version change"
NEW_TESTFILE=TEST-file.to-be-removed.txt
touch $NEW_TESTFILE
git add $NEW_TESTFILE
git commit -m "Add test file to ensure we are required to bump"
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
git diff ${BASEBRANCH}..HEAD --name-only | grep -v .bumpversion.cfg | sort > actual.lst
cat actual.lst | sed "/$NEW_TESTFILE/d" > actual-trimmed.lst
diff expected.lst actual-trimmed.lst || exit 1
rm expected.lst actual.lst actual-trimmed.lst

echo "TEST STEP: version changes detected & ok now"
version_checker || exit 1
git push origin ${NUBRANCH} --dry-run || exit 1

echo "TEST STEP: create merge conflicts using a new branch based on the original and bump with a different part"
git checkout ${BASEBRANCH}
git checkout -b ${NUNUBRANCH}
bump2version major --commit || exit 1
git merge ${NUBRANCH}
git commit -m "this shouldn't work..." && exit 1  # expect conflicts...

echo "TEST STEP: manually the python files which are needed to get version checker to run..."
git checkout ${NUNUBRANCH} -- version_checker/*.py
git commit -m "this still shouldn't work..." && exit 1  # expect conflicts...

echo "TEST STEP: auto resolve merge conflicts with cli utility and verify no more issues"
version_checker --merge
git commit -m "this should work..." || exit 1  # expect conflicts resolved...

echo "TEST FINISH"

echo "TEST CLEANUP"
git checkout ${PREVBRANCH} || echo "WARNING: couldn't check out ${PREVBRANCH} not erroring in case expected from detached head..."
git branch -D ${NUBRANCH}
git branch -D ${NUNUBRANCH}

echo "Done. everything seems ok"
