from mypkg import gitpython
from mypkg import parse_diff
from mypkg.parse_diff import Context
from mypkg import operate_git
from mypkg import make_patch
from mypkg.make_patch import Context
import inspect
import os

def main():
    path = os.getcwd()
    repo = gitpython.get_repo(path)
    diffs = gitpython.get_diffs(repo)
    # patches = [ gitpython.make_patch(d.a_path, d.diff.decode()) for d in diffs ]
    # for patch in patches:
    #     print(patch)
    # gitpython.auto_commit(repo, patches)
    repo = operate_git.get_repo(path)
    diffs = operate_git.get_diffs(repo)
    
    for diff in diffs:
        context = Context()
        context.parse_diff(diff.diff.decode())

        for ac in context.add_chunks:
            patch_code = context.make_add_patch(ac)
            patch = gitpython.make_patch(diff.a_path, patch_code)
            print(patch)
            gitpython.auto_commit(repo, patch, diff.a_path, ac.start_id, ac.end_id)

        for rc in context.remove_chunks:
            patch_code = context.make_remove_patch(rc)
            patch = gitpython.make_patch(diff.a_path, patch_code)
            print(patch)
            gitpython.auto_commit(repo, patch, diff.a_path, rc.start_id, rc.end_id)

if __name__ == '__main__':
    main()
