# SearchMark API

Backend of SearchMark's paid feature: given a web page and an account's bookmark folder tree, recommend the folder for the bookmark. Also holds the accounts and the credits that pay for it.

## Language

### Recommendation

**Analysis**:
The title and summary of a web page. Produced once per URL and shared by every account.
_Avoid_: summary, page analysis, step 1

**Folder path**:
The full path of a folder from the root of the tree. The only unambiguous name for a folder, since leaf names repeat (ten folders are called `Tools`).
_Avoid_: folder name, label, category

**Recommendation**:
The folder path chosen for a page given one account's folder tree, optionally with the name of a new folder to create under it. The unit the account pays for.
_Avoid_: suggestion, classification, prediction

**Model**:
The LLM that produces analyses and recommendations. One model for both, chosen on the golden set.

### Billing

**Account**:
A person using the paid feature, identified by a verified email address.
_Avoid_: user, customer, client

**Credit**:
The right to one recommendation. The single unit of billing: every offer is expressed in credits.
_Avoid_: token, request, call, quota

**Free allowance**:
The credits every new account receives once, at creation.
_Avoid_: trial, freemium, free tier

**Pack**:
A fixed number of credits bought in one payment. Credits from a pack never expire.
_Avoid_: plan, subscription, bundle, top-up

**Ledger**:
The append-only record of every credit movement of an account. The balance is the sum of the ledger.
_Avoid_: balance table, wallet, counter

### Evaluation

**Golden set**:
Curated URLs from the owner's own bookmarks, each with the expected folder path and a note saying why that folder and not its tempting neighbours.
_Avoid_: test set, fixtures, samples

**Verdict**:
How a recommendation compares to the expected folder path: `exact` (same path), `related` (parent, child or sibling), `miss` (anything else).
_Avoid_: score, result, accuracy

**Baseline**:
The golden set verdicts of the model currently in production. A candidate model must match it to be considered.
