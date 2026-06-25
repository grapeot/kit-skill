# GitHub Setup Notes

This file records the external GitHub steps for the Kit skill repository. Do not run these commands until the user explicitly confirms external repo creation/push timing.

## Intended Repository

- Owner: `grapeot`
- Repository: `kit-skill`
- Visibility: public
- Default branch: `master`

## Local Branch

The local repository is initialized with `master`:

```bash
git init --initial-branch=master
```

## Create Public Repo Without Pushing

```bash
gh repo create grapeot/kit-skill --public --description "AI-first Kit broadcast publishing CLI skill"
git remote add origin git@github.com:grapeot/kit-skill.git
```

## Push When Approved

```bash
git push -u origin master
```

## Branch Protection After First Push

Branch protection usually requires the branch to exist on GitHub. After `master` is pushed, configure protection with zero required reviewers:

```bash
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  /repos/grapeot/kit-skill/branches/master/protection \
  -f required_status_checks='null' \
  -f enforce_admins=false \
  -f required_pull_request_reviews='{"required_approving_review_count":0}' \
  -f restrictions='null' \
  -f allow_force_pushes=false \
  -f allow_deletions=false
```

If GitHub rejects the JSON fields with `-f`, use an explicit JSON body instead:

```bash
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  /repos/grapeot/kit-skill/branches/master/protection \
  --input - <<'JSON'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```
