# Garleak Specification

**Spec version 0.3, draft for comment, 2026-09-21**

| | |
|---|---|
| Status | Draft circulated for public comment. Not yet binding on any implementation. |
| Covers | Objects and stages, identity and accountability, scoring, the credit economy, versions, and the rules they depend on (graduation, screening, gated categories, governance). |
| License | This specification is dedicated to the public domain under CC0 1.0. Copy it, fork it, quote it without attribution. |
| Comments | File one issue per rule or open question in the project repository and put the rule number in the title (for example "§6.3.2" or "OQ-4"). |

## Changelog

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-09-14 | First draft for comment. |
| 0.2 | 2026-09-14 | Assistance is declared on two ordinal axes, writing (W0 to W3) and analysis (A0 to A2), in place of L0 to L4 (§4.5, §4.7, §11.6 to §11.9). OQ-7 is resolved, OQ-21 is closed by the new scale, and OQ-23 and OQ-24 are new. New §3.7 on identity and visibility in the static Phase 1 implementation (RFC 0001), with matching notes in §3.2.1, §3.3.1, §5.2.6, and §11. §6.1.4 and §9.3.1 updated for the static implementation. Code license stated as AGPL-3.0-or-later (§9.8.4). |
| 0.3 | 2026-09-21 | The second object type is renamed from "scratch" to "sketch" throughout, including identifiers (`sketch:8812`) and addresses (`/sketch/`). No rule changes with the name. Category listings show the most recent entries (`recent_count`, default 50) instead of a fixed window of days, so nothing drops off a listing because time passed. Submissions are open. |

## Notes for reviewers

This document turns sections 3 through 7 of the project's master plan into rules, and pulls in the parts of sections 8, 9, 10, and 12 that those sections depend on. Where the plan was silent or inconsistent, this draft says so rather than choosing quietly. The changes relative to the plan are these.

- The plan's screening section points to "§11" for gated categories and plagiarism screening. Both live in the plan's safety section (§10). In this document they are §9 and §8.3.
- The plan does not say whether a paper may carry a pseudonym before graduation. Its stage diagram ties graduation to real names, while the design shows sketches under handles and papers under real names. This draft proposes a default and lists it as OQ-1.
- The plan uses both "Verified" and "Graduated" for graduation. Here "Graduated" is the graduation state, and "Verified" always carries a stage ("Verified T2"), so the word never stands alone as an endorsement.
- The plan's assistance codes L0 to L4 were categories that mixed two questions, who wrote the text and who did the analysis, so no single order fit them and a community "median" had no meaning. Version 0.2 replaces them with two ordinal axes (§4.5.2), which resolves OQ-7.
- Version 0.2 also records the move to a static implementation built from a public git repository (RFC 0001). The rules do not change, but a few cannot be met in its first phase, and §3.7 says which.
- "v1" in the plan means the original submission. Because versions are numbered major.minor, this document writes it `v1.0`.

Every decision the plan leaves open is marked in the text as **Proposed default, open for comment** with a number, and collected in §12. Those are the places where comments are most useful.

---

## 1. Scope, conventions, and terms

### 1.1 What this document covers

Garleak is a planned open archive for research papers and research ideas produced with help from AI models. Every object carries a declared provenance and a public verification record. The question the archive asks of a paper is not whether a model wrote it but whether it holds up.

This document defines what the archive holds, the stages objects move through, who is accountable for them, how they are checked, how the credit system that gates submission works, and how versions are tracked. The reference implementation, the rubrics in `packages/rubrics`, and the `citecheck` service are bound by it. Where code and this document disagree, this document wins until an RFC changes it.

### 1.2 What Garleak is not

**1.2.1** Garleak MUST NOT describe anything it does as publication, as peer review, or as the work of a journal. The words "published" and "real paper" MUST NOT appear in the interface, the terms, exports, or generated documents to describe an object or its state. The states Garleak uses are admitted, Verified (always with a stage, §1.4), and Graduated.

**1.2.2** Admitted never means endorsed. Admission means an object passed screening for scope and form (§8). It carries no claim about correctness, novelty, or value. The terms, the submission page, the header of every object page, and every page of every generated PDF MUST say so (§8.7, §9.3).

**1.2.3** Archiving on Garleak is not prior publication. The terms MUST say so, and MUST say that nothing in them restricts later submission of the same work to a journal. Journals set their own policies, so the submission page SHOULD advise authors to check the policy of any journal they plan to use.

**1.2.4** A verification stage says which rubric items a named person checked on a named version, under a named rubric version, and nothing more. It is narrower than peer review and MUST NOT be presented as equivalent to it.

**1.2.5** Garleak is not anonymous. Identity is held, not absent (§3.3).

### 1.3 Conventions

**1.3.1** The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, and OPTIONAL are to be read as described in RFC 2119 and RFC 8174 when, and only when, they appear in capitals.

**1.3.2** Rules are numbered section.subsection.rule and set in bold at the start of the paragraph, so a comment can cite "§5.6.3". Unnumbered paragraphs are explanation and are not binding.

**1.3.3** A rule marked **Proposed default, open for comment (OQ-n)** states what an implementation SHOULD do until question n in §12 is closed by an RFC or a later version of this document.

**1.3.4** Values written `config.name` live in the versioned configuration file described in §10.4. The values given here are the opening values.

**1.3.5** Times are UTC and written in RFC 3339 format. "Day" means a rolling 24-hour period unless stated otherwise.

### 1.4 Terms

| Term | Meaning |
|---|---|
| Object | A paper or a sketch. The unit that gets an identifier. |
| Paper | A full write-up with a claim and an argument. Checked for correctness (§2.1.2). |
| Sketch | An idea, observation, or fragment. Checked for novelty, not correctness (§2.1.3). |
| Version | One immutable state of an object's content, numbered major.minor (§6.2). |
| Stage | Where a version sits on its ladder. T0 to T4 for papers, N0 to N3 for sketches. "Tier" means a paper stage. |
| Field | A subject area (for example physics or mathematics). Credits, standing, moderators, and listings are scoped by field. |
| Rubric family | A kind of claim with its own checklist (computational, mathematics, and later others). A paper declares one or more (§4.2.3). Distinct from field. |
| Rubric | A versioned YAML file listing the items a verifier checks at each tier (§10.3). |
| Verification | A record by one verifier, on one exact version, at one stage, under one rubric version (§4.2). |
| Novelty check | The verification record for a sketch (§4.4). |
| Fix | A proposed change to a version, shaped like a pull request (§6.7). |
| Maintainer | The account that may merge or decline fixes on a paper (§6.8). |
| Contributor | An account listed on a version, because it submitted the object or authored a merged fix (§6.5). |
| Accountable human | The human account answerable for an action (§3.1). |
| Agent account | An account that acts for an AI system, registered and answered for by a human operator (§3.4). |
| Operator | The human account responsible for an agent account. |
| Independent | A verifier who is not a contributor and has no shared affiliation or recent co-authorship with any contributor (§3.6). |
| Standing | A per-field measure of a verifier's record (§4.6). |
| Admitted | Passed screening for scope and form. Never an endorsement. |
| Verified Tn | Holds stage Tn under §2.4. The bare word "Verified" is not used without a stage. |
| Graduated | The state a paper version reaches under §7. |

---

## 2. Objects and stages

### 2.1 Object types

**2.1.1** Garleak holds two object types, papers and sketches. The submitter chooses the type at upload. The stage is earned through verification and is never chosen by the submitter.

**2.1.2** A paper is a full write-up with a claim and an argument. Papers are checked for correctness against the T1 citations rubric and the rubric of each rubric family the paper declares.

**2.1.3** A sketch is an idea, an observation, or a fragment, often one that came out of a conversation with a model. A sketch SHOULD take minutes to post. Sketches are checked for novelty (has this been done?), which is a literature question, and never for correctness.

**2.1.4** An object's type MUST NOT change after admission. A moderator MAY change the type during screening, before admission (§8.4.1). The only route from a sketch to a paper is promotion (§2.6), which creates a new object.

### 2.2 Separation of the two streams

**2.2.1** Papers and sketches MUST have separate listings, separate identifier sequences, separate stage ladders, separate visual treatment, and separate credit costs. A listing page MUST NOT contain both types.

**2.2.2** T stages MUST NOT be applied to sketches, and N stages MUST NOT be applied to papers. There is no T3 or T4 equivalent for a sketch.

**2.2.3** A sketch MUST NOT be citable in a way that implies a result. Its citation string MUST call it an idea record (§2.3.8).

### 2.3 Identifiers

**2.3.1** Every object receives a type and a number at submission. Papers and sketches are numbered from separate sequences of positive integers. A number is never reused, even after removal. `paper:4471` and `sketch:4471` are unrelated objects.

**2.3.2** Identifiers follow this grammar (ABNF, RFC 5234).

```
identifier   = type ":" number [ version ]
type         = "paper" / "sketch"
number       = nonzero *DIGIT
version      = "v" major [ "." minor ]
major        = nonzero *DIGIT
minor        = "0" / ( nonzero *DIGIT )
nonzero      = %x31-39
```

**2.3.3** Identifiers resolve as follows.

| Form | Example | Resolves to | Stable? |
|---|---|---|---|
| Concept | `paper:4471` | The latest admitted version of the object | Moves as versions are added |
| Series | `paper:4471v3` | The latest minor version within major 3 | Moves only on minor bumps, which never change a claim |
| Exact | `paper:4471v3.2` | Exactly version 3.2 | Immutable |

**Proposed default, open for comment (OQ-3).** The series form resolves to the latest minor in that major, not to `v3.0`. Minor versions never change a claim (§6.3), so a reader following a series identifier always reaches the best wording of the same claims. Anyone who needs the exact bytes cites the exact form.

**2.3.4** `v1` written alone in prose or in the interface means `v1.0`, the original submission. As an identifier, `paper:4471v1` follows the series rule in §2.3.3.

**2.3.5** The type prefix MUST appear in every identifier Garleak displays, exports, or prints in a citation string. A bare number MAY appear only in a listing row where the object type is printed beside it.

**2.3.6** Verification records, fixes, credit events, and dataset exports MUST refer to versions by exact identifier.

**2.3.7** Nothing ever 404s. Every well-formed identifier that was ever issued MUST resolve, to the object, to a tombstone (§9.6), or to a page that says what exists. A well-formed identifier that was never issued MUST resolve to a page that says so and lists what does exist.

**2.3.8** Citation strings take these forms. The stage and date in the string are those at the time the string was generated.

```
Paper version:
  <authors>. <title>. Garleak paper:4471v3.2 (Verified T2, not peer reviewed,
  stage as of 2026-09-14). https://garleak.org/abs/4471v3.2/

Graduated version (§7.3):
  <authors>. <title>. Garleak paper:4471v3.2, Graduated 2026-10-02 (T3).
  <DOI if issued, see OQ-16>

Sketch:
  <handle or name>. "<one-line statement>". Garleak sketch:8812v1.0,
  idea record, not a result, posted 2026-09-14.
```

### 2.4 Paper stages

| Tier | Name | Meaning |
|---|---|---|
| T0 | Unverified | No tier is held. |
| T1 | Citations checked | Every reference exists and says what the paper claims it says. Universal across all fields, and always first. |
| T2 | Claims checked | The claims pass the T2 items of each declared rubric family. |
| T3 | Partially reproduced | The central result was partially reproduced (for proofs, independently re-checked; see the mathematics rubric). |
| T4 | Independently reproduced | Reproduced by a verifier independent of every contributor (§3.6). |

**2.4.1** Stages belong to versions, never to papers. A paper's displayed stage is the stage of its current version. The paper page SHOULD also show the highest stage any version has held, with that version's identifier.

**2.4.2** Tiers are cumulative. A version holds Tn only if it holds every tier below n.

**2.4.3** For each version and each tier, the tier status is computed from the active verifications (§4.2) at that tier.

| Status | Condition |
|---|---|
| none | No active verification at this tier |
| passed | At least one active passing verification, and no active failing one |
| failed | At least one active failing verification, and no active passing one |
| contested | At least one active passing and at least one active failing verification |
| pending | Passed, but one or more items were re-opened by a minor bump and await re-check (§6.3.3) |

**2.4.4** The tier of a version is the highest n such that every tier from T1 to Tn has status passed or pending. If T1 is not passed or pending, the version is T0. A version whose tier includes a pending status MUST show a pending marker beside its tier and MUST NOT graduate.

**2.4.5** A verification MAY be recorded at a tier above the version's current tier. It counts once every lower tier is held.

**2.4.6** A contested tier opens a dispute automatically (§4.3).

**2.4.7** A T4 verification counts only if its verifier is independent of every contributor to the version (§3.6) and the verification carries no loop label (§5.6). The implementation MUST refuse to record a T4 verification from a verifier who is not independent.

**2.4.8** A paper whose declared rubric families have no approved rubric can reach T1 and no higher, until an RFC approves a rubric for that family.

**2.4.9** T2, T3, and T4 each require a passing verification against every rubric family the version declares, at that tier. One verification record covers one rubric, so a version with two families needs two records per tier.

**2.4.10** Stage movement is shown below. Downward moves happen only through the events named. A new major version starts at T0 and leaves the stages of earlier versions untouched.

```
             T1 passed        T2 passed        T3 passed        T4 passed
      T0 ------------> T1 ------------> T2 ------------> T3 ------------> T4

  Downward, on the same version:
    a counted verification is overturned, withdrawn, or voided (§4.3, §5.6)
    a failing verification makes a tier contested (§2.4.3)
  New version:
    minor bump   carries verifications forward, some items may become pending (§6.3.3)
    major bump   new version starts at T0 (§6.3.4)
```

### 2.5 Sketch stages

| Stage | Name | Meaning |
|---|---|---|
| N0 | Posted | Nobody has looked yet. |
| N1 | No prior work found | Searched, no close prior work found. The checker says where they looked. |
| N2 | Prior work found and linked | Informative, not a failure. |
| N3 | Judged tractable | Someone judged the idea tractable and said what testing it would take. |

**2.5.1** Sketch stages belong to versions, like paper stages.

**2.5.2** N1 requires a novelty check with a search record: the sources searched, the queries or search strategy, the date, and the closest items found with a sentence on why each is not close.

**2.5.3** N2 requires a novelty check that names at least one prior work by a resolvable reference and states how it overlaps the sketch. N2 MUST be displayed neutrally. Its label, color, and wording MUST NOT suggest failure, rejection, or fault.

**2.5.4** N1 and N2 are alternative outcomes, not steps. A later check that finds prior work moves an N1 sketch to N2, and the earlier N1 record stays visible. An N2 sketch returns to N1 only if a later check addresses each linked prior work and shows it does not overlap.

**2.5.5** N3 requires an earlier N1 or N2 record on the same version, plus a tractability note that says what testing the idea would take (data, method, rough effort). The display MUST show which path led there, as "N3, no prior work found" or "N3, prior work linked".

**2.5.6** Novelty checks carry no claim about correctness, and the interface MUST NOT imply one.

**2.5.7** Any account MAY post a non-exclusive claim of intent to test a sketch. Claims carry no priority and expire after `config.sketch_claim_days` (opening value 90). The sketch row shows "unclaimed" or the number of active claims.

```
      N0 ----> N1 (no prior work found) ---- later check finds prior work ----> N2
       \                                                                         ^
        \--------------------------> N2 (prior work linked) --------------------/
      N1 or N2 ---- tractability note ----> N3 (shows which path)
```

### 2.6 Promotion

**2.6.1** When someone tests a sketch and writes up the result, the write-up is submitted as a new paper whose `promoted_from` field holds the exact sketch version identifier. This is promotion. The paper is a new object with its own number, its own v1.0, and its own stages.

**2.6.2** The backlink is permanent on both objects. The paper's maintainer MUST NOT be able to remove it. The sketch page lists every paper promoted from it.

**2.6.3** Anyone may test a sketch and promote it, including its author. Promotion needs no permission from the sketch's author. One sketch MAY be promoted into several papers.

**2.6.4** The paper shows its origin inline, for example "promoted from sketch:8812v1.0 by u/kestrel". The sketch author's name is shown as the sketch shows it. Promotion MUST NOT reveal the held identity of a pseudonymous sketch author.

**2.6.5** When a promoted paper is admitted, the sketch author receives a promotion credit event in the paper's field (§5.3). Promotion is also the attribution the plan describes, and the attribution does not depend on the credit.

**2.6.6** Any account MAY file a claim that an admitted paper derives from a sketch but lacks the backlink. A moderator decides the claim and records the reasoning. An upheld claim adds the backlink and the credit event.

**2.6.7** Promotion is not a stage. The sketch keeps its N stage and gains a "promoted" marker.

---

## 3. Identity and accountability

### 3.1 The accountable human

**3.1.1** Every submission, version, fix, verification, novelty check, vote, contest, dispute, and appeal MUST have an accountable human. There are no exceptions. For a human account the accountable human is the account holder. For an agent account it is the operator (§3.4).

### 3.2 Identity paths

**3.2.1** ORCID is the primary identity path. An account created this way records the ORCID iD, confirmed through ORCID's OAuth flow or, in the Phase 1 implementation, through the account holder's public ORCID record (§3.7.2).

**3.2.2** A verified institutional email address is the second path. It MUST be available, because ORCID coverage is thin in some fields (law and the humanities especially) and those fields cannot take part without it. The email domain SHOULD be mapped to a Research Organization Registry (ROR) identifier where one exists.

**3.2.3** Each account records which path verified it (`identity_path`). Both paths permit every action in this document. Conflict checks (§3.6) use whatever data each path provides and record which sources they used.

**3.2.4** Every human account MUST declare its current affiliations at signup and keep them current. Declared affiliations are held data (§3.3.8) and are used for conflict checks.

### 3.3 Held identity and display

**3.3.1** Identity is held, not absent. Garleak knows the verified identity of every human account. The signup and submission pages MUST state this in plain words, in the sense of "We know who you are. Nobody else does, unless you say so," adjusted to match whichever display rules are in force (OQ-1, OQ-2) and the limits of the implementation in use (§3.7).

**3.3.2** Each human account has one public handle (written `u/name`) and one real name. For each object, a contributor chooses whether that object shows their handle or their real name.

**3.3.3** A sketch MAY show its author's handle at every stage.

**3.3.4** **Proposed default, open for comment (OQ-1).** A paper MAY show contributors' handles until graduation. A version can graduate only when every human contributor, and the operator of every contributing agent, shows a real name on it (§7.1). A contributor who does not want to show a real name blocks graduation of that version and nothing else.

**3.3.5** Switching an object from handle to real name applies to the whole object, including earlier versions, and cannot be undone.

**3.3.6** **Proposed default, open for comment (OQ-2).** Every verification and novelty check shows the verifier's real name. The verification record is the archive's product, and it is only worth as much as the accountability of the person who made it.

**3.3.7** When a conflict flag (§3.6.5) involves a party shown by handle, the flag MUST state only its type (shared affiliation or recent co-authorship). It MUST NOT name the institution or the co-author, since that would reveal the pseudonymous party.

**3.3.8** Garleak MUST NOT disclose held identity or held affiliation data except with the holder's consent, under legal compulsion, or to a named moderator handling a specific conflict, removal, or takedown case. Every such disclosure MUST be logged with its reason.

### 3.4 Agent accounts

**3.4.1** Agent accounts are permitted and first-class. Each is registered by a human account with a verified identity, which becomes its operator. The registration records the agent's name, the model or models it runs with versions, a description of or link to the software that runs it, and the operator.

**3.4.2** On every object an agent account submits or contributes to, the agent is shown as author and the operator is shown as responsible party. The operator's display follows §3.3 like any other contributor.

**3.4.3** The operator's credits pay for the agent's submissions. Spend events are written to the operator's ledger in the relevant field (§5.4). Agent accounts hold no balance.

**3.4.4** Agent accounts have a hard daily submission quota, much tighter than the human one (§5.6.7). The operator also has a total quota across all of their agents.

**3.4.5** Agent accounts are excluded from gated categories entirely (§9.1). They MUST NOT submit, contribute fixes, vote, or appear in any role on a gated object.

**3.4.6** Every submission from an agent account is held for human screening, whatever its type (§8.2).

**3.4.7** **Proposed default, open for comment (OQ-5).** Agent accounts MUST NOT record verifications, novelty checks, or community votes. They MAY author fixes, which earn no credit. Output of automated tools, including agents, MAY be attached as evidence to a human verifier's record.

**3.4.8** Operators MUST NOT pass agent output through a human account to avoid the agent quota or the autonomous track. A moderator who finds this MAY move the object to the autonomous track and suspend the accounts involved, with a stated reason.

**3.4.9** An operator MAY suspend or retire their agent account. A retired agent's objects stay in the archive with the operator still shown as responsible party.

### 3.5 Tracks

**3.5.1** Every object belongs to one of two tracks, fixed at submission. Objects submitted by an agent account are in the autonomous track. Objects submitted by a human account are in the human-prompted track.

**3.5.2** Leaderboards, digests that rank, and dataset exports MUST keep the two tracks separate. No public aggregate may pool them unless track is shown as a dimension of the aggregate.

### 3.6 Independence and conflicts

**3.6.1** Two human accounts have a **shared affiliation** when both list the same institution (at the ROR identifier level) at any point within `config.conflict_window_months` of the check.

**3.6.2** Two human accounts have a **recent co-authorship** when they appear together as authors on any work dated within `config.conflict_window_months` of the check, in ORCID works, Crossref, OpenAlex, or a self-declaration.

**3.6.3** **Proposed default, open for comment (OQ-6).** `config.conflict_window_months` is 48. Affiliation is compared at the institution level, not the department level.

**3.6.4** An agent account inherits its operator's affiliations and co-authorships for every conflict check.

**3.6.5** A verifier V is **independent** of a version X when all of the following hold. V is not a contributor to X or to any earlier version of the same object. V is not the operator of an agent that contributed to X. V has no shared affiliation and no recent co-authorship with any human contributor to X or with the operator of any contributing agent.

**3.6.6** A verifier who is not independent MAY still record verifications at T1, T2, and T3. Each such verification MUST carry a public conflict flag stating its type, subject to §3.3.7.

**3.6.7** T4 (§2.4.7) and graduation (§7.1) require independence.

**3.6.8** Every verification records the data sources and the date used for its conflict check. When the data change later, the check is re-run. A newly found conflict adds a flag. If it breaks the independence that T4 or graduation relied on, the consequences in §4.3.5 and §7.4 follow.

**3.6.9** Before recording a T4 verification, the verifier MUST attest that they know of no shared affiliation, co-authorship within the window, or other close working relationship with any contributor that the automated check missed. A false attestation is grounds for voiding the verification and its credit.

### 3.7 Identity in the Phase 1 implementation

The first implementation is a static site built from a public git repository. Submissions and verifications arrive as GitHub issue forms that become pull requests (RFC 0001). That design costs nothing to run, and it makes some of the rules above impossible to meet. This section says which, so that no page promises more than the implementation delivers. The maintainer decided on 2026-09-14 to open with these limits and to add the Phase 2 service (§3.7.6) later.

**3.7.1** In Phase 1 every action (submission, verification, novelty check, fix, vote, contest, dispute, appeal) is made from a GitHub account. The account that opens an issue or pull request is public, so its handle is public data attached to every record it creates.

**3.7.2** In Phase 1 an account completes the ORCID path by listing its GitHub profile URL on its public ORCID record. The implementation reads the record through ORCID's public API and records the ORCID iD. The institutional email path is checked by hand. The account holder writes to the contact address from the institutional address, and a moderator records the result.

**3.7.3** The link between a GitHub account and an ORCID record is public on the ORCID side, so anyone who looks can connect an ORCID-verified GitHub account to a real name. Phase 1 therefore cannot keep held identity (§3.3) private for any account verified through ORCID. It can keep held identity private only for accounts verified through the institutional email path, where the moderator keeps the evidence outside the repository.

**3.7.4** While Phase 1 is in use, the signup and submission pages MUST replace the sentence in §3.3.1 with an accurate one, in the sense of "Your GitHub account is public, and so is the ORCID link that verifies it. If you need a pseudonym, verify by institutional email instead."

**3.7.5** Data marked R or H in §11 MUST NOT be committed to the public repository. Held data used for conflict checks, such as affiliations, is kept by moderators outside the repository, and only the result of the check is recorded. Some restricted records cannot stay restricted in Phase 1. Every credit event follows from public records, so anyone can compute any account's balance, which breaks §5.2.6. A community vote cast through GitHub shows its voter. The page that collects such a record MUST say that it is public.

**3.7.6** Phase 2 is an option that is also free to run. A Cloudflare Worker with ORCID sign-in accepts submissions and commits them to the repository with a bot token, so the submitter's GitHub account and ORCID link never appear in the public record, and §3.3 can be met as written. The maintainer decided on 2026-09-14 to open with Phase 1 and add the Worker later (RFC 0001).

**3.7.7** A GitHub issue is public from the moment it is opened. In Phase 1 a paper, or a submission in a gated category, is therefore visible on GitHub before it is screened, which breaks §8.2.1 and §8.2.3 on GitHub, though not on the site, which shows nothing until the pull request is merged. **Proposed default, open for comment (OQ-24).** In Phase 1, submissions in gated categories are not accepted through public issue forms. They go to the contact address, or wait for a private intake path such as the Phase 2 Worker.

---

## 4. Scoring

### 4.1 Separate signals

**4.1.1** Garleak computes no composite score. The stage (§2.4, §2.5), the three assistance signals (§4.5), verifier standing (§4.6), and `pct_original` (§6.6) MUST NOT be combined into a single number for display, ranking, or export. A listing MAY be sorted by any one of them.

### 4.2 Verifications of papers

**4.2.1** A verification is a record made by one human verifier, on one exact version, at one tier, under one rubric identified by id and version. The record MUST name the rubric id and version (§10.3). A verification attaches to a version and never to a paper.

**4.2.2** The T1 rubric (`citations`) is universal across all fields. T2 to T4 use field rubric families. The first two are computational and mathematics. Planned families are empirical and medical (studies exist and report what is claimed), law (cases and statutes exist and are still good law), and humanities (quotations and sources exist and say what is claimed). Each needs an RFC before use.

**4.2.3** Each version declares one or more rubric families. The submitter declares them. A moderator MAY correct them during screening, and a fix MAY change them in a new version.

**4.2.4** A verifier MUST record a verdict for every item the rubric lists at the tier being verified. The verdict is pass, fail, or not applicable. A not-applicable verdict is allowed only where the rubric item says when it applies, and MUST carry a reason. Each verdict MUST carry the evidence the item requires (for example a link, a log, or a commit hash).

**4.2.5** A verification passes when every required item at that tier is pass or justified not applicable. It fails when any required item fails. Advisory items are recorded and shown but do not decide the outcome.

**4.2.6** Automated reports, such as a `citecheck` run, MAY be attached as evidence. An automated report is never a verification by itself. The human verifier is responsible for every verdict in the record, including verdicts that agree with an automated report.

**4.2.7** A verifier SHOULD record the time spent and SHOULD declare any model use while verifying, in free text. Time spent is part of the dataset the archive exists to produce, the cost to a human of making machine-generated research correct.

**4.2.8** A verifier MUST NOT verify a version to which they contributed.

**4.2.9** Verifications are public, released under CC0, and never deleted. A verification's status is one of active, withdrawn, overturned, or void. Every status change records who made it, when, and why.

**4.2.10** A verifier MAY withdraw their own verification with a stated reason. A withdrawn verification stays visible, stops counting toward any tier, and its credit is reversed (§5.2.1).

**4.2.11** Failing verifications are displayed with the same prominence as passing ones, in the same list, ordered by date. They MUST NOT be hidden, collapsed, or placed below passing ones. Hiding them would bias the whole archive upward.

### 4.3 Disputes and overturns

**4.3.1** Any human account with field standing (§4.6.3) MAY dispute an active verification, naming the disputed items and giving evidence. A contested tier (§2.4.6) opens a dispute covering the items on which the conflicting verifications differ.

**4.3.2** **Proposed default, open for comment (OQ-4).** A dispute is resolved by a new verification of the disputed items only, made by a verifier who is independent of the version's contributors and who is neither the original verifier nor the disputant. If the new verdict differs from the original on any disputed item, the original verification is overturned. Otherwise the dispute closes and the original stands. A dispute with no resolving verification after `config.dispute_open_days` (opening value 60) stays open and is shown as open.

**4.3.3** An overturned verification stays visible, marked overturned with a link to the resolving record. It stops counting toward any tier and lowers its verifier's standing (§4.6). Its credit is not reversed, since standing already carries the consequence and reversing credit would discourage honest checking.

**4.3.4** A dispute is itself a public record and is kept in the dataset.

**4.3.5** When a later conflict check (§3.6.8) shows that a counted T4 verification was not independent, the verification loses its T4 standing, and the tier is recomputed. If the verifier's attestation (§3.6.9) was false, the verification is voided.

### 4.4 Novelty checks of sketches

**4.4.1** A novelty check is recorded by one human on one exact sketch version. Its outcome is N1, N2, or N3, with the contents required by §2.5.2, §2.5.3, or §2.5.5.

**4.4.2** Novelty checks use the same statuses, withdrawal rules, dispute rules, and display rules as paper verifications. They need no rubric file in this version of the spec. A novelty rubric MAY be added by RFC.

**4.4.3** A sketch's author MUST NOT record a novelty check on their own sketch.

### 4.5 Assistance

Assistance is declared on two axes, because who wrote the text and who did the analysis are separate questions. Each axis carries three signals, and the signals are always shown separately.

| Signal | Source |
|---|---|
| Declared | The submitter, one code on each axis (§4.5.2) |
| Predicted | Garleak's classifier, an estimate on each axis, shown with an interval |
| Community | Reader votes on each axis, shown as a distribution and a median |

**4.5.1** The three signals MUST be stored, displayed, and exported separately, side by side, and within each signal the two axes MUST be kept separate. Signals MUST NOT be averaged, merged, weighted together, or reduced to one field, and the two axes MUST NOT be combined into one level, in the interface, the API, or any export.

**4.5.2** The declared assistance uses exactly these two scales. Each is ordinal, and a higher number means more model involvement on that axis.

| Code | Writing |
|---|---|
| W0 | A human wrote it. |
| W1 | A human wrote it, and a model polished it. |
| W2 | A model drafted it, and a human edited it. |
| W3 | A model wrote it, with light or no human edits. |

| Code | Analysis |
|---|---|
| A0 | A human did the analysis. |
| A1 | A model assisted with the analysis (code or derivations), and a human checked it. |
| A2 | A model did the analysis. |

Analysis means the work behind the claims, such as calculations, code, derivations, proofs, data handling, and the choice of method. The two scales are not comparable with each other. Implementations MUST NOT add, subtract, or otherwise combine a W code with an A code, and MUST NOT do arithmetic on the numbers in the codes beyond ordering them.

**Proposed default, open for comment (OQ-23).** A paper declares both axes. A sketch declares the writing axis and MAY leave the analysis axis empty when it contains no analysis. An empty analysis axis is shown as "no analysis", never as A0.

**4.5.3** Every version MUST carry a declaration made by its accountable human. The declaration records one code on each axis (subject to OQ-23), every model used (name, provider, and version or date), other AI tools used, a provenance statement in free text, and an OPTIONAL link to transcripts or logs. The declaration describes the version as a whole, as it stands.

**4.5.4** A declaration MAY be amended. An amendment is a new record, and the history of declarations for a version stays visible.

**4.5.5** The predicted assistance is produced per version by a classifier identified by id and version. For each axis it predicts, a prediction records a probability for each code on that axis, the most probable code, and a 90% interval, given as the smallest range of adjacent codes on that axis that holds at least 90% of the probability. A classifier MAY predict one axis only, and the other axis then shows no prediction. A prediction MUST be labeled as an estimate wherever it appears.

**4.5.6** The classifier never overrides a declaration. The predicted codes MUST NOT be used in screening, credit accounting, stage computation, visibility, ranking, or any other decision about an object or account. Copy MUST NOT describe a gap between declared and predicted codes, on either axis, as an error, a violation, or a suspicion. There is no penalty for high model use on Garleak, which is why this is one place where a classifier can be calibrated honestly.

**4.5.7** Any contributor to a version MAY contest its prediction on either axis with a written statement. The contest is recorded and shown next to the prediction. Contests are not adjudicated, do not remove the prediction, and are kept in the dataset as calibration data. A new classifier version produces new prediction records and keeps the old ones.

**4.5.8** Any human account with a verified identity that is not a contributor to a version MAY cast one community vote on that version, choosing one code on each axis or on one axis only. A later vote by the same account replaces its earlier vote, and both are kept in history. The display shows the full distribution of votes on each axis.

**4.5.9** Within each axis, codes are ordered by their number (W0 < W1 < W2 < W3 and A0 < A1 < A2). The community median is computed on each axis separately and shown once that axis has at least `config.community_min_votes` votes (opening value 5). When the two middle votes differ, both codes are shown (for example "W1 to W2"), since no code lies between them. This rule replaces the ordering proposed for L0 to L4 in version 0.1 and resolves OQ-7.

**4.5.10** The gap between declared and predicted codes is recorded per version and per axis, and released in the dataset. It is the archive's main research output on disclosure.

### 4.6 Verifier standing

**4.6.1** Standing is kept per verifier per field. It rises with verifications that survive and falls when verifications are overturned. It MUST be recomputable from the public record.

**4.6.2** **Proposed default, open for comment (OQ-8).** Standing in field F equals S minus 3 times O. S is the number of the verifier's verifications and novelty checks in F that have been active for at least 90 days and never overturned. O is the number overturned. Verifications with a loop label (§5.6) are left out of S.

**4.6.3** **Proposed default, open for comment (OQ-8).** An account has field standing in F when its standing in F is at least `config.field_standing_min` (opening value 5). Field standing is required to approve community merges (§6.8.3) and to open disputes (§4.3.1).

**4.6.4** Standing is shown beside the verifier's name. It describes the verifier's record, not the paper.

### 4.7 Display

**4.7.1** A paper version's page MUST show the current stage with numeral and label (never color alone), each verifier's name with the rubric items they passed and failed, the rubric id and version, the date, any conflict or loop label, and every failing, withdrawn, and overturned verification. It MUST also show the version count, `pct_original`, the three assistance signals for each axis side by side with any contests, the track, and any gated or community-maintained marker.

**4.7.2** A listing row MUST show the stage, the version count, `pct_original` for papers, and the declared code on each axis (for example "W2 A1 declared"). A listing row MUST NOT show a single-number summary.

**4.7.3** Any featured or ranked selection (§7.6) MUST show `pct_original` and the declared and predicted levels on each featured object.

---

## 5. The credit economy

Generating a paper costs a model user almost nothing, so unlimited free submission would bury the archive within a week. Checking is the scarce resource, and few people volunteer for it. Credits address both problems. Verifying earns credits, and submitting spends them.

### 5.1 Principles

**5.1.1** Verifying earns credits and submitting spends them. Credits are the only access control on submission.

**5.1.2** Garleak MUST NOT charge money for submission, verification, or any function tied to them. A fee would read as pay-to-publish, which is the association the project most needs to avoid.

**5.1.3** Credits MUST NOT be bought, sold, or transferred between accounts. An agent spending from its operator's balance (§3.4.3) is not a transfer. Bounties, if added later, MUST NOT be convertible into credits.

### 5.2 The ledger

**5.2.1** Credits are recorded in an append-only ledger of credit events. No event is edited or deleted. A correction is a new reversal event that references the event it reverses.

**5.2.2** Credits are field-scoped. Every event carries exactly one field, and credits earned in field F can be spent only in F. A single global pool would be farmed in the easy fields and spent in the hard ones.

**5.2.3** The field of an event is the primary field of the object involved.

**5.2.4** The balance of an account in a field is the sum of its events in that field. It MUST be recomputable from the ledger alone.

**5.2.5** Every event records the configuration version in effect when it was written (§10.4).

**5.2.6** An account's ledger is visible to the account holder, to a moderator handling a case that involves it, and to auditors named in the terms. It MUST NOT be public, because it would link pseudonymous submissions to named verifications. Aggregate statistics are public. The Phase 1 implementation cannot meet this rule (§3.7.5).

### 5.3 Earning

| Event | Opening amount | Config key |
|---|---|---|
| Paper verification, any tier, pass or fail | +1.0 | `config.earn.verification` |
| Novelty check on a sketch | +0.5 | `config.earn.novelty_check` |
| Merged fix | +2.0 | `config.earn.merged_fix` |
| Screening or appeal decision by a moderator | +1.0 | `config.earn.moderation` |
| Promotion of the account's sketch into an admitted paper | +1.0 | `config.earn.promotion` |

**5.3.1** **Proposed default, open for comment (OQ-9).** The amounts above are the opening values. Every paper verification earns the same amount whatever its tier.

**5.3.2** `config.earn.merged_fix` MUST be greater than `config.earn.verification`. A merged fix is harder work than a verification.

**5.3.3** A verification earns the same whether it passes or fails. A rule that paid more for passing would pay people to pass things.

**5.3.4** Moderation earns at the same rate as verification. It is the same kind of unpaid work and carries the same standing.

**5.3.5** These earn nothing. Fixes merged by their own author. Fixes and other actions by agent accounts. Verifications, fixes, and approvals on edges of a detected loop (§5.6.3). Verifications that are withdrawn or voided (their credit is reversed).

### 5.4 Spending

| Event | Opening amount | Config key |
|---|---|---|
| Paper submission (a new paper object, including promoted papers and forks) | -2.0 | `config.spend.paper` |
| Sketch submission | -1.5 | `config.spend.sketch` |
| New version of an existing object | 0 | none |

**5.4.1** The opening ratio is two verifications per paper, the value of `config.spend.paper` divided by `config.earn.verification`. It is tighter for sketches. **Proposed default, open for comment (OQ-9).** A sketch costs 1.5, which is three novelty checks or one and a half paper verifications.

**5.4.2** New versions cost nothing. Fixing should never be the expensive path.

**5.4.3** **Proposed default, open for comment (OQ-10).** A human account's balance in a field MAY fall to `config.balance_floor` (opening value -2.0), so a new account can submit one paper before it has verified anything ("Post yours, check two others"). A submission that would take the balance below the floor MUST be refused.

**5.4.4** Agent submissions spend from the operator's balance, and the balance floor for agent submissions is 0.

**5.4.5** **Proposed default, open for comment (OQ-9).** When screening rejects a submission, its spend event is reversed, except for rejections under the criterion for spam, test posts, and non-research.

### 5.5 Configuration and tuning

**5.5.1** All earn and spend amounts, the ratio they imply, and the balance floor live in the versioned configuration (§10.4). Changing any of them requires an RFC (§10.1).

**5.5.2** The amounts are expected to be tuned from real throughput. The signal to watch is the verification ratio, verifications per submission. If it stays below 1.0, the ratio is wrong.

### 5.6 Anti-gaming

Reciprocal verification rings will form in the first month. The rules below assume that.

**5.6.1** The verification graph is a directed graph on accounts. An edge runs from a verifier to each human contributor and each operator of each contributing agent on a version they verified or novelty-checked. An edge also runs from each account that merges or approves a fix (§6.8) to the fix's author. Every edge carries the timestamp of the action that created it.

**5.6.2** A loop is a directed cycle of length 2, 3, or 4 in which every edge was created within `config.loop_window_days` of every other edge in the cycle.

**5.6.3** Every action on an edge that belongs to a detected loop earns nothing. If credit was already written, a reversal event is written. The affected records carry a public label that says "reciprocal loop" and gives the loop length. The label MUST NOT name a party shown by handle.

**5.6.4** **Proposed default, open for comment (OQ-11).** `config.loop_window_days` is 180. Loop-labeled verifications still count toward T1, T2, and T3, with the label visible, but MUST NOT count toward T4, graduation, or standing.

**5.6.5** Loop detection MUST be deterministic, MUST run whenever an edge is added and again on a daily schedule, and its code MUST be public. A loop label is removed only if an edge in the loop is shown to be wrong, for example a misattributed contributor.

**5.6.6** Verification has a daily rate limit, since careful checking is slow and a burst is a signal. **Proposed default, open for comment (OQ-12).** A human account MAY record at most 5 paper verifications and 10 novelty checks per day across all fields. More than 3 records within one hour are flagged for moderator review but not blocked.

**5.6.7** **Proposed default, open for comment (OQ-12).** Submission quotas per day are 3 papers and 10 sketches for a human account; 1 paper and 3 sketches for each agent account; and 2 papers and 6 sketches for an operator summed over all their agents.

**5.6.8** Shared affiliation and recent co-authorship are allowed below T4, flagged, and visible (§3.6.6). T4 requires no shared affiliation or co-authorship with any contributor (§2.4.7).

**5.6.9** A moderator MAY void credit events found to be gamed, after review and with a written reason given to the account. The void is a reversal event, and the reason is kept in the moderation record.

---

## 6. Versions and fixes

### 6.1 Immutability

**6.1.1** `v1.0` of every object is immutable forever. For a paper it is the raw model output as submitted, and it is the scientific object the archive measures against.

**6.1.2** Every version, not only `v1.0`, is immutable once created. A change to content always makes a new version.

**6.1.3** The only exception is removal under §9.6 (legal order, harm, plagiarism, or material the submitter had no right to post). Removal hides content behind a tombstone and is recorded. It never edits a version. Where the law allows, removed bytes MAY be kept under restricted access for audit.

**6.1.4** Storage format is not fixed by this document. An implementation MAY store later versions as diffs against `v1.0`, or as whole files in a git repository as the Phase 1 implementation does, provided every version can be rebuilt byte for byte and its content hash checked.

### 6.2 Numbering

**6.2.1** Versions are numbered major.minor, starting at `1.0`. A minor bump goes from n.m to n.(m+1). A major bump goes from n.m to (n+1).0.

**6.2.2** Each object has a linear trunk. Every version except `v1.0` has exactly one parent, the version before it. There are no branches inside an object. Genuine divergence becomes a fork (§6.4).

**6.2.3** Identifiers map to versions as set out in §2.3.3.

### 6.3 Major and minor changes

**6.3.1** A change is major if it changes any of the following.

- A claim, conclusion, or the statement of a theorem, lemma, or definition.
- A reported number, uncertainty, or table value.
- The data behind a figure, or what a figure plots.
- A method, derivation, or proof step.
- Code, data, or environment artifacts cited as the basis of a result.
- Which references support a central claim, by adding or removing support. Correcting the metadata of a reference, or replacing a reference that does not exist or does not say what is claimed with one that supports the same unchanged statement, is not major.

**6.3.2** Every other change is minor. Examples are wording, typos, formatting, clarifications that leave every item in §6.3.1 unchanged, reference metadata corrections, and the reference replacements allowed in §6.3.1.

**6.3.3** A minor bump carries every active verification and novelty check on the parent forward to the new version. A carried record is marked with the exact identifier of the version where it was made. These items are re-opened and become pending (§2.4.3).

- T1 items for every reference that was added or replaced, or whose citing sentence changed.
- Every item that a merged fix in the bump says it addresses (§6.7.1).

A pending item is resolved by a re-check, which is a verification limited to the pending items. Any verifier MAY make it, subject to the usual rules.

**6.3.4** A major bump clears verifications. The new version starts at T0 (or N0 for a sketch). The parent keeps its records. New verifications MAY cite evidence recorded on earlier versions.

**6.3.5** **Proposed default, open for comment (OQ-22).** Carrying a verification forward does not need the verifier's consent. The verifier is notified and MAY decline the carry within `config.carry_decline_days` (opening value 30). Declining removes the carried record from the new version only. It is not a withdrawal, and credit is not reversed.

**6.3.6** The maintainer states the bump type. The implementation SHOULD flag minor bumps that touch numbers, mathematics, tables, figure data, code or data artifacts, or references, and show the flag on the version.

**6.3.7** Any verifier whose record was carried to a minor version, and any account with field standing, MAY challenge the minor classification within `config.bump_challenge_days` (opening value 30, OQ-14). A moderator decides and records the reasoning. If the challenge is upheld, the version keeps its number and gains a permanent "reclassified as claim-changing" marker, its carried records are removed from it (they remain on the parent), and its stage is recomputed as for a major version. Versions built on it inherit the recomputation.

### 6.4 Forks

**6.4.1** Anyone MAY fork a paper from any exact version. A fork is a new paper object whose `forked_from` field holds that exact identifier. The backlink is permanent on both objects.

**6.4.2** A fork's `v1.0` holds the content of the source version, unchanged, and is marked as a fork base. The fork is a paper submission for credit (§5.4) and screening (§8). The forking account is its submitter. The source's contributors are listed as inherited, with the source identifier.

**6.4.3** A fork's `pct_original` is measured against the `v1.0` of the root of its lineage (the first object in the chain of `forked_from` links), and the display names that root.

### 6.5 Contributors and assistance per version

**6.5.1** Each version carries its own contributor list and its own assistance declaration (§4.5.3). By the sixth version the authorship is often not the first version's authorship, and the page MUST make that visible.

**6.5.2** The contributor list of a version is the contributor list of its parent, plus the authors of fixes merged into it, plus its submitter. Each entry records the account, its roles (submitter, fix author, maintainer), and the first version it contributed to.

**6.5.3** The version page SHOULD show how the contributor list differs from that of `v1.0`.

### 6.6 `pct_original`

**6.6.1** Every paper version MUST display `pct_original` on its page and in listing rows. It is the guard against papers being quietly edited until they are good, at which point they measure nothing. It is a measure of text, not of credit. A T3 paper that is 40% human-rewritten is a different object from an untouched one, and the number says so.

**6.6.2** **Proposed default, open for comment (OQ-15).** `pct_original` is computed by algorithm `po-1`, as follows.

1. **Rendition.** Produce the canonical text rendition of each version with the pinned extractor named in `config.text_extractor`. Use the LaTeX or Markdown source when the version has one, and the PDF text layer otherwise. The rendition includes the title, abstract, section headings, body text, footnotes, figure and table captions, table cell text, appendices, and mathematics (as source). It excludes the author and affiliation block, acknowledgments and funding statements, the reference list, figure and image content, code, data, and supplementary files, platform stamps and notices, the assistance declaration, source comments, and citation, reference, and label keys.
2. **Normalize.** Apply Unicode NFKC normalization and case folding. Replace each LaTeX control word by its name (`\alpha` becomes `alpha`). Remove remaining markup characters.
3. **Tokenize.** A token is a maximal run of characters in the Unicode categories L (letters) and N (numbers). Everything else separates tokens.
4. **Shingle.** With k = `config.po_k` (opening value 5), let G(v) be the set of k-token sequences that occur at consecutive positions in the token sequence of v.
5. **Cover.** A token position in version n is covered if at least one k-gram that includes it is in G(`v1.0`). Let C be the number of covered positions and |n| the number of tokens in version n.
6. **Compute.** `pct_original` = 100 × C / |n|. The companion value `pct_v1_retained` is computed the same way in the other direction, as the share of `v1.0` token positions covered by k-grams in G(version n).

The display rounds to the nearest integer, with halves rounded up. The stored record keeps C, |n|, the retained counts, k, the algorithm id, and the extractor id and version, so anyone can recompute both values from the public renditions.

**6.6.3** The reasons for this definition, for reviewers. Plain longest-common-subsequence over word tokens counts scattered function words ("the", "of", "a") that happen to fall in order, so even a complete rewrite would score as partly original. Requiring runs of k tokens removes most chance matches. The definition depends only on sets of k-grams, so it has no tie-breaking and no dependence on a diff implementation. A moved paragraph still counts as original text, which is what the number is meant to say. `pct_original` answers "how much of this version is still the original text"; `pct_v1_retained` answers "how much of the original is still here". Both are recorded because each misses what the other catches (heavy additions versus heavy cuts).

**6.6.4** Worked example with k = 5. Version 1.0 reads "We fit the rotation curve with a single exponential disk and find a flat outer profile" (16 tokens). A later version reads "We fit the rotation curve with a single exponential disk plus a bulge and find a slowly falling outer profile" (20 tokens). The first ten tokens of the later version lie inside 5-grams that occur in version 1.0. None of the others do, since "and find a" and "outer profile" survive only in runs shorter than five. So C = 10, `pct_original` = 50, and `pct_v1_retained` = 10/16, displayed as 63.

**6.6.5** Edge cases. For `v1.0`, both values are 100. If version n has no tokens, `pct_original` is shown as "n/a". If `v1.0` has no tokens, `pct_original` is 0 for any version with tokens, and `pct_v1_retained` is "n/a". A change only to excluded parts (for example replacing a figure image) leaves both values unchanged. A version with fewer than k tokens covers nothing.

**6.6.6** The reference implementation MUST ship test vectors (pairs of renditions with expected C, |n|, and retained counts) covering at least the cases in §6.6.4 and §6.6.5. A change to the algorithm, k, or the exclusion list is an RFC (§10.1) and gets a new algorithm id. Values computed under an old id are kept, and new values are stored beside them.

**6.6.7** Sketches MAY display `pct_original` under the same definition. Listing rows for sketches do not have to show it.

### 6.7 Fixes

**6.7.1** A fix is shaped like a pull request. It records the exact base version, a diff against that version's source, a rationale, the author, the author's declared model use for the fix, the proposed bump type, and OPTIONAL links to the verification items it addresses.

**6.7.2** A fix is open, merged, declined, withdrawn, or superseded. A decline MUST give a short reason. Every state change is recorded with who made it and when.

**6.7.3** Every new version is made by merging one or more fixes into the current version. A maintainer's own edits are fixes they author and merge themselves. Such self-merged fixes earn no credit (§5.3.5). A version made from several fixes takes the major bump if any of them is major.

**6.7.4** A fix whose base is not the current version MUST be brought up to date before it is merged. The implementation MAY do this automatically when the change applies cleanly.

**6.7.5** Merging a fix into a Graduated version creates a new major version (§7.3).

**6.7.6** The author of a merged fix earns `config.earn.merged_fix` in the paper's field, subject to §5.3.5.

### 6.8 Maintainers and community maintenance

**6.8.1** The submitter maintains a paper by default and MAY add human co-maintainers. For an agent-submitted paper, the operator is the maintainer.

**6.8.2** **Proposed default, open for comment (OQ-13).** A paper becomes community-maintained when any open fix has had no maintainer action (merge, decline, or comment) for `config.inactivity_days`, opening value 90.

**6.8.3** On a community-maintained paper, a fix merges when two accounts with field standing (§4.6.3) approve it, and is declined when two such accounts decline it with reasons. Neither may be the fix's author or the operator of an agent that authored it. Approvals are edges in the verification graph (§5.6.1) and carry conflict flags like verifications.

**6.8.4** A returning maintainer MAY take the paper back by acting on its open fixes. Merges made during community maintenance stand.

**6.8.5** The paper page shows when a paper is community-maintained and since when.

---

## 7. Graduation

### 7.1 Conditions

**7.1.1** A paper version graduates when all of the following hold at the time of the request.

1. Its tier is T3 or T4, with no pending item and no contested tier.
2. At least two distinct verifiers hold active, passing, loop-free verifications on it at T2 or above, and at least one of them holds the T3 or T4 verification.
3. Each of those two verifiers is independent of the version (§3.6.5), and the two share no affiliation with each other.
4. No fix is open against the version, and no dispute is open on any of its verifications.
5. Every human contributor, and the operator of every contributing agent, shows a real name on the object (§3.3.4, OQ-1).

**7.1.2** The plan's rule is "two independent verifiers, no shared affiliation". This document reads "independent" as it does for T4 (§3.6.5), which adds recent co-authorship to shared affiliation.

### 7.2 Process

**7.2.1** A maintainer requests graduation. The implementation checks §7.1.1 automatically and records the result. Graduation involves no editorial judgment. A refused request states which condition failed.

**7.2.2** A request asks every contributor shown by handle to confirm a switch to real name (§3.3.5). Graduation waits until every one has confirmed, or the request is withdrawn.

### 7.3 Effects

**7.3.1** A Graduated version gets a distinct visual state, a stable citation string (§2.3.8), and a place in a separate Graduated listing.

**7.3.2** Graduation freezes that version. No minor version may follow it. Any merged fix creates a new major version, which starts at T0.

**7.3.3** **Proposed default, open for comment (OQ-16).** DOIs are minted only for Graduated versions, through Zenodo, as a version DOI for each Graduated version and a concept DOI for the paper that resolves to its latest Graduated version. Minting DOIs for T0 material would lend it the look of a citable result.

### 7.4 Withdrawal of graduation

**7.4.1** Graduation is withdrawn automatically when any condition in §7.1.1 stops holding because a counted verification is overturned, withdrawn, or voided, or a conflict check removes a verifier's independence. An open fix or open dispute filed after graduation does not withdraw it, but it is shown on the page.

**7.4.2** A withdrawn graduation stays on the record with its date and reason. The version's citation string then carries "graduation withdrawn" and the date. Any DOI stays registered and its landing page shows the withdrawal.

### 7.5 Naming

**7.5.1** The state is called Graduated. It MUST NOT be called "published", "accepted", or a "real paper", and copy MUST NOT imply that graduation is peer review.

### 7.6 Features and digests

**7.6.1** A daily digest of new admitted objects is purely mechanical. A weekly most-verified list is computed automatically.

**7.6.2** A monthly feature picks from that month's graduations. Its criteria are public, its picker is named, and it selects on verification depth and what was learned, not on how impressive the result sounds. A verifier of the month runs alongside it.

**7.6.3** Every featured object shows `pct_original` and its declared and predicted levels (§4.7.3). A monthly feature invites polishing before submission, which contaminates `v1.0`, and these numbers keep that visible.

---

## 8. Screening and admission

### 8.1 Scope

**8.1.1** Every object is read by the screening process, before public visibility for papers and shortly after for sketches (§8.2).

**8.1.2** Screening checks admissibility, never quality. The only questions are these.

1. Is this a genuine attempt at research, rather than spam, a test post, or nonsense?
2. Is it in scope and in the correct category?
3. Does it belong in a gated category (§9.1) that it was not filed under?
4. Does it contain anything harmful, defamatory, or plagiarized, or material the submitter had no right to post?

**8.1.3** Screening MUST NOT consider whether the work is good, correct, novel, interesting, well written, or written in fluent English, and MUST NOT consider the declared or predicted assistance level. That is what verification is for. Once screening judges quality, the platform has an editor and every rejection becomes an argument it owns.

**8.1.4** A submission that belongs in a gated category is reclassified into it and held, not rejected.

### 8.2 Asymmetry by type

**8.2.1** A paper is screened before it becomes publicly visible.

**8.2.2** A sketch becomes visible as soon as it passes the automated first pass (§8.3), and is removed afterwards if a human finds it fails §8.1.2.

**8.2.3** Anything in a gated category is held for human review before any visibility, whatever its type.

**8.2.4** Every submission from an agent account is held for human review, whatever its type.

**8.2.5** **Proposed default, open for comment (OQ-14).** Held submissions SHOULD receive a decision within `config.hold_target_days` (opening value 7). The share of holds decided within the target is made public (§8.6).

### 8.3 Automated first pass

**8.3.1** The first pass is automated. A human sees only what it flags, plus a random calibration sample.

| Check | Source |
|---|---|
| Plagiarism against Crossref and open corpora | existing screening service, run on every `v1.0` |
| Fabricated or unresolvable citations | `citecheck` |
| Near-duplicate of an existing submission | content hashing and embedding similarity |
| Gated-category content filed elsewhere | classifier over title, abstract, and body |
| Harmful content | classifier tuned for recall over precision |
| Empty, truncated, or non-research submissions | heuristics |

**8.3.2** The automated pass MAY admit or flag. It MUST NOT reject. Only a human moderator rejects or removes.

**8.3.3** The assistance classifier MUST NOT be part of the first pass (§4.5.6).

**8.3.4** Every automated result records the check id, its version, and its score.

**8.3.5** **Proposed default, open for comment (OQ-12).** The calibration sample is `config.screen_sample_rate` of unflagged submissions, opening value 5%.

**8.3.6** The target is fewer than 10% of submissions reaching a human. If the share rises above that, the automated pass is tightened rather than more moderators recruited.

### 8.4 Decisions, reasons, and appeals

**8.4.1** A screening decision is one of admit, reclassify (category, gated status, or type, before admission only), hold, reject, or remove (after admission).

**8.4.2** The admission criteria MUST be public in full, with each criterion numbered.

**8.4.3** Every rejection and removal MUST state a specific reason that cites a numbered criterion.

**8.4.4** Each decision may be appealed once. The appeal MUST be reviewed by a different moderator from the one who made the decision. **Proposed default, open for comment (OQ-14).** An appeal may be filed within 30 days of the decision and SHOULD be decided within 14 days of filing. The appeal decision is final on Garleak and is recorded.

### 8.5 Moderators

**8.5.1** Moderators are per field, recruited on the same schedule as rubric maintainers, and named publicly.

**8.5.2** Moderators earn credits at the verification rate (§5.3.4), subject to the rate limits in config.

**8.5.3** A moderator MUST recuse from any decision on an object they contributed to, or where they are not independent of a contributor (§3.6.5).

### 8.6 Transparency

**8.6.1** Garleak MUST release quarterly counts of submissions, holds, rejections by criterion, removals by criterion, appeals and their outcomes, the share reaching a human, and the share of holds decided within target.

### 8.7 Admitted never means endorsed

**8.7.1** The terms, the submission page, the header of every object page, and the PDF stamp (§9.3) MUST say that screening checks scope and form only, and that admission carries no claim about correctness. Someone will eventually argue that Garleak approved what they acted on, and this sentence is the answer.

---

## 9. Gated categories, visibility, and removal

### 9.1 Gated categories

**9.1.1** The gated categories are clinical, legal, financial, pharmacological, and structural engineering. The list changes only by RFC.

**9.1.2** A gated paper is held for human screening (§8.2.3) and is not publicly visible below T1. Below T1 it is visible only to its contributors, to moderators, and to signed-in human accounts with a verified identity that have opted in to gated verification, so that T1 can be done.

**9.1.3** Agent accounts are excluded from gated categories in every role (§3.4.5).

**9.1.4** **Proposed default, open for comment (OQ-17).** A gated sketch is held for human screening and, once admitted, is visible only to signed-in human accounts with a verified identity. It is never publicly visible and always carries `noindex`, since sketches have no T1 to pass.

### 9.2 Indexing and metadata

**9.2.1** Every T0 paper version, and every gated object below T1, MUST carry `noindex`. The concept page of a paper carries `noindex` while its current version is T0. This limits citation laundering.

**9.2.2** **Proposed default, open for comment (OQ-18).** Non-gated sketches MAY be indexed once they pass the automated first pass. Their structured metadata MUST mark them as idea records, not as scholarly articles.

**9.2.3** Every object page and every export carries the stage, the rubric versions behind it, and the date, in machine-readable metadata.

### 9.3 The PDF stamp

**9.3.1** Every page of every PDF Garleak provides for download MUST carry a stamp inside the PDF. PDFs travel without the web page, so the stamp must travel with them. The stamp is generated when the downloadable PDF is produced. In the static implementation that happens at every site build, so a stage change reaches the stamp with the next build. For a paper the stamp reads, in substance, as follows.

> Garleak paper:4471v3.2. Not peer reviewed. Admitted after screening for scope and form only; admission is not endorsement. Stage T2 as of 2026-09-14. Current record: https://garleak.org/abs/4471v3.2/

**9.3.2** A sketch PDF, if one is served, says "idea record, not a result" in place of the stage sentence.

### 9.4 Plagiarism

**9.4.1** Every `v1.0`, including fork bases, is screened for plagiarism against Crossref and open corpora (§8.3.1).

### 9.5 Submitters' rights

**9.5.1** Submitters post only their own work and their own model output. Garleak is not a venue for other people's unpublished material, and the terms MUST say so in a sentence.

### 9.6 Removal and takedown

**9.6.1** Garleak MUST name a responsible person publicly and MUST keep a working takedown path, with a response target stated in the terms.

**9.6.2** Content removed for a legal order, harm, plagiarism, or lack of rights is hidden behind a tombstone. The identifier still resolves, and the tombstone states the date and the criterion. Verification records stay visible unless they themselves quote removed content, in which case the quoting passages are removed and the rest of the record stays.

**9.6.3** Removal never edits a version (§6.1.3), and every removal is recorded in the moderation log.

### 9.7 Withdrawal by the author

**9.7.1** **Proposed default, open for comment (OQ-19).** A maintainer MAY withdraw a paper, and a sketch author MAY withdraw a sketch. Withdrawal adds a public notice with a reason, stops new verifications and credit on the object, and leaves every version accessible. Nothing is deleted, because `v1.0` and the verification record are the dataset. Only removal under §9.6 hides content.

### 9.8 Licenses

**9.8.1** Paper and sketch content is released under a license the submitter chooses from a short list, with CC BY 4.0 as the default.

**9.8.2** Verification records, novelty checks, declarations, predictions, votes, and all other metadata are released under CC0.

**9.8.3** Dataset releases are licensed CC BY, with a DOI and a citation string.

**9.8.4** Code in the reference implementation, including the site generator, `citecheck`, and the rubric validator, is licensed AGPL-3.0-or-later.

---

## 10. Governance of the instrument

The tiers, the rubrics, and the credit ratio are the scientific instrument. Changing them without a record breaks comparison across time, which is the main thing the archive measures.

### 10.1 What needs an RFC

**10.1.1** The tier and stage definitions (§2.4, §2.5), every rubric, and the credit amounts and ratio (§5.3, §5.4) change only by RFC.

**10.1.2** **Proposed default, open for comment (OQ-20).** The following are also treated as part of the instrument and change only by RFC: the assistance taxonomy (§4.5.2) and its ordering (§4.5.9), the `pct_original` algorithm and its parameters (§6.6), the loop rule (§5.6.2), the independence rule (§3.6), the standing formula (§4.6.2), and the list of gated categories (§9.1.1).

**10.1.3** Operational parameters (quotas, rate limits, screening thresholds, the calibration sample rate, target times) change by a public commit to the configuration file with a changelog entry, without an RFC.

### 10.2 RFC process

**10.2.1** RFCs live in the repository's `rfcs/` directory, are numbered, and follow its template, which requires a section on comparability across time.

**10.2.2** Discussion runs for at least 14 days. A rubric RFC SHOULD be reviewed by at least one verifier with standing in an affected field.

**10.2.3** The maintainer decides at first. A steering committee with per-field rubric maintainers takes over at roughly 20 active contributors. Rejected RFCs are kept with their reasoning.

**10.2.4** An accepted RFC names the new version of what it changes and the date it takes effect. No RFC applies retroactively. Records made before the date keep the versions they were made under.

**10.2.5** Sponsors, including model developers, have no role in RFC decisions or rubric content. Garleak lists every sponsor publicly and says so.

### 10.3 Rubric versioning

**10.3.1** Every rubric file has a stable id and a semantic version (MAJOR.MINOR.PATCH). A MAJOR bump changes the pass criteria of an existing item, adds a required item, or deprecates an item. A MINOR bump adds an advisory item or clarifies wording without changing any pass criterion. A PATCH fixes typos or formatting.

**10.3.2** Every verification records the rubric id and version it used. New verifications MUST use the current active version of each rubric. A verifier cannot choose an older one.

**10.3.3** Verifications made under an older rubric version keep it and are not re-scored. The version page SHOULD note when a newer MAJOR version of a rubric it relies on exists.

**10.3.4** Rubric item ids are stable. An item is never renumbered, and an id is never reused. An item that is no longer wanted is deprecated and kept in the file.

**10.3.5** The rubric file format is defined by the JSON Schema in `packages/rubrics/schema/rubric.schema.json`.

### 10.4 Configuration

**10.4.1** Every `config.` value in this document lives in one versioned configuration file. Each credit event, loop label, prediction, and `pct_original` value records the configuration version in effect.

### 10.5 This document

**10.5.1** Versions 0.x of this document are drafts for comment. Version 1.0 will follow the first comment period. After 1.0, changes to any rule in the scope of §10.1 need an RFC, and other changes need a pull request with a changelog entry.

**10.5.2** Every record Garleak writes carries enough version information (spec, rubric, configuration, classifier, algorithm, extractor) to be interpreted under the rules in force when it was made.

---

## 11. Data model

This section lists the fields each object carries in records and exports. Storage may differ, for example versions stored as diffs against `v1.0`. The record format in `archive/FORMAT.md`, and the validation CI runs on it, follow these tables. In Phase 1 the records are files in a public repository, so only fields marked P can be stored there (§3.7.5).

**11.0.1** Field names are normative for the API and for exports. An implementation MAY add fields. It MUST NOT drop, merge, or rename the fields below.

**11.0.2** Types used below. `id` is an opaque string, except object and version ids, which follow §2.3.2. `ts` is an RFC 3339 UTC timestamp. `ref(X)` is the id of an X. `wcode` is one of W0 to W3, and `acode` is one of A0 to A2 (§4.5.2). Lists are written `[type]`.

**11.0.3** Visibility. **P** is public and CC0. **R** is restricted to the account holder, moderators on a case, and named auditors. **H** is held identity data, disclosed only under §3.3.8.

### 11.1 Account

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | id | P | |
| `kind` | `human` or `agent` | P | |
| `handle` | string | P | `u/name` |
| `github` | string or null | P | The GitHub account that acts for this account in Phase 1 (§3.7.1). Public by construction. |
| `real_name` | string | H | Shown only on objects where the account chooses real name |
| `identity_path` | `orcid` or `institutional_email` | P | In Phase 1, `orcid` is checked through the public ORCID record (§3.7.2) |
| `orcid` | string | H | Public where the account shows its real name, and in Phase 1 for every account verified through ORCID (§3.7.3) |
| `email_domain` | string | H | Mapped to a ROR id where possible |
| `affiliations` | [{`ror_id`, `name`, `start`, `end`, `source`}] | H | Used for conflict checks (§3.6) |
| `standing` | [{`field`, `value`, `computed_at`}] | P | Derived (§4.6) |
| `operator` | ref(Account) | P | Agent accounts only |
| `agent_profile` | {`name`, `models`: [{`name`, `provider`, `version`}], `runner_url`, `registered_at`} | P | Agent accounts only |
| `status` | `active`, `suspended`, or `retired` | P | |
| `created_at` | ts | P | |

### 11.2 Paper

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | `paper:N` | P | |
| `primary_field` | string | P | Scopes credits (§5.2.3) |
| `cross_list_fields` | [string] | P | |
| `track` | `human-prompted` or `autonomous` | P | Fixed at submission (§3.5) |
| `gated` | boolean | P | |
| `maintainers` | [ref(Account)] | P | |
| `community_maintained_since` | ts or null | P | §6.8 |
| `promoted_from` | exact sketch version id or null | P | §2.6 |
| `forked_from` | exact paper version id or null | P | §6.4 |
| `lineage_root` | exact version id | P | `v1.0` used for `pct_original` |
| `status` | `screening`, `admitted`, `withdrawn`, or `removed` | P | |
| `withdrawal` | {`at`, `reason`} or null | P | §9.7 |
| `content_license` | string | P | §9.8 |
| `current_version` | exact version id | P | Derived |
| `created_at` | ts | P | |

### 11.3 Sketch

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | `sketch:N` | P | |
| `primary_field` | string | P | |
| `track` | `human-prompted` or `autonomous` | P | |
| `gated` | boolean | P | §9.1.4 |
| `author` | ref(Account) | P | Shown as handle or real name per §3.3 |
| `promoted_to` | [ref(Paper)] | P | §2.6.2 |
| `claims` | [{`account`, `created_at`, `expires_at`}] | P | §2.5.7 |
| `status` | `admitted`, `withdrawn`, or `removed` | P | |
| `content_license` | string | P | |
| `created_at` | ts | P | |

### 11.4 Version

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | exact version id | P | For example `paper:4471v3.2` |
| `object` | ref(Paper or Sketch) | P | |
| `major`, `minor` | integer | P | |
| `parent` | exact version id or null | P | Null only for `v1.0` |
| `bump` | `initial`, `minor`, or `major` | P | |
| `merged_fixes` | [ref(Fix)] | P | §6.7.3 |
| `reclassified` | {`by`, `at`, `reason`} or null | P | §6.3.7 |
| `submitted_by` | ref(Account) | P | Accountable human (§3.1) |
| `source_format` | `latex`, `markdown`, `text`, or `pdf` | P | |
| `content_hash` | sha256 hex | P | Checked on every rebuild |
| `rendition_hash` | sha256 hex | P | Canonical text rendition (§6.6.2) |
| `statement` | string | P | Sketches only, one line |
| `rubric_families` | [string] | P | Papers only (§4.2.3) |
| `contributors` | [Contributor] | P | §6.5 |
| `declarations` | [ref(AssistanceDeclaration)] | P | History, latest is current |
| `stage` | `T0`-`T4` or `N0`-`N3` | P | Derived (§2.4.4, §2.5) |
| `tier_status` | map of tier to `none`, `passed`, `failed`, `contested`, or `pending` | P | Derived (§2.4.3) |
| `pct_original` | {`value`, `covered`, `tokens`, `retained_value`, `retained_covered`, `v1_tokens`, `algorithm`, `k`, `extractor`, `config_version`} | P | §6.6 |
| `graduation` | {`state`, `graduated_at`, `withdrawn_at`, `reason`, `doi`} or null | P | §7 |
| `created_at` | ts | P | |

### 11.5 Contributor (entry in a version)

| Field | Type | Vis | Notes |
|---|---|---|---|
| `account` | ref(Account) | P | |
| `roles` | [`submitter`, `fix_author`, `maintainer`, `inherited`] | P | |
| `first_version` | exact version id | P | |
| `display` | `handle` or `real_name` | P | Per object (§3.3.2) |
| `inherited_from` | exact version id or null | P | Forks (§6.4.2) |

### 11.6 AssistanceDeclaration

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | id | P | |
| `version` | exact version id | P | |
| `writing` | wcode | P | §4.5.2 |
| `analysis` | acode or null | P | Null only for a sketch with no analysis (OQ-23) |
| `models` | [{`name`, `provider`, `version_or_date`}] | P | |
| `tools` | [string] | P | |
| `provenance` | text | P | |
| `transcript_url` | url or null | P | |
| `declared_by` | ref(Account) | P | |
| `declared_at` | ts | P | |
| `supersedes` | ref(AssistanceDeclaration) or null | P | §4.5.4 |

### 11.7 Prediction

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | id | P | |
| `version` | exact version id | P | |
| `classifier` | {`id`, `version`} | P | |
| `writing` | {`probabilities`, `point`, `interval`, `interval_mass`} or null | P | `probabilities` maps each wcode to a number and sums to 1. `interval` is a range of adjacent codes (§4.5.5) and `interval_mass` is at least 0.9. Null when the classifier does not predict this axis. |
| `analysis` | {`probabilities`, `point`, `interval`, `interval_mass`} or null | P | As for `writing`, over acodes |
| `computed_at` | ts | P | |
| `config_version` | string | P | |

### 11.8 Contest

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | id | P | |
| `prediction` | ref(Prediction) | P | |
| `axis` | `writing` or `analysis` | P | §4.5.7 |
| `contested_by` | ref(Account) | P | A contributor to the version |
| `statement` | text | P | |
| `created_at` | ts | P | |

### 11.9 CommunityVote

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | id | R | |
| `version` | exact version id | P | |
| `voter` | ref(Account) | R | Public output shows only the distribution |
| `writing` | wcode or null | P | Counted in the public distribution for this axis |
| `analysis` | acode or null | P | At least one of `writing` and `analysis` is set (§4.5.8) |
| `cast_at` | ts | P | |
| `replaces` | ref(CommunityVote) or null | R | §4.5.8 |

### 11.10 Verification

Covers paper verifications, novelty checks, and re-checks.

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | id | P | |
| `version` | exact version id | P | The version it counts on |
| `carried_from` | ref(Verification) or null | P | Set on carried records (§6.3.3) |
| `kind` | `paper`, `novelty`, or `recheck` | P | |
| `tier` | `T1`-`T4` | P | Paper and re-check only |
| `rubric` | {`id`, `version`} | P | Paper and re-check only (§10.3.2) |
| `outcome` | `pass`, `fail`, `N1`, `N2`, or `N3` | P | Derived for papers (§4.2.5) |
| `verifier` | ref(Account) | P | Human only |
| `items` | [{`item_id`, `verdict`, `reason`, `evidence`: [{`kind`, `value`}], `automated_report`}] | P | `verdict` is `pass`, `fail`, or `na` |
| `search_record` | {`sources`, `queries`, `searched_at`, `closest`: [{`ref`, `why_not_close`}]} | P | Novelty only (§2.5.2) |
| `prior_work` | [{`ref`, `overlap`}] | P | Novelty only (§2.5.3) |
| `tractability_note` | text | P | N3 only (§2.5.5) |
| `time_spent_minutes` | integer or null | P | §4.2.7 |
| `verifier_model_use` | text or null | P | §4.2.7 |
| `conflict_flags` | [{`type`, `computed_at`, `sources`}] | P | Redacted per §3.3.7 |
| `independent` | {`value`, `computed_at`, `sources`} | P | §3.6.5 |
| `t4_attestation` | {`text`, `at`} or null | P | §3.6.9 |
| `loop_label` | {`length`, `detected_at`} or null | P | §5.6.3 |
| `status` | `active`, `withdrawn`, `overturned`, or `void` | P | |
| `status_history` | [{`status`, `by`, `at`, `reason`}] | P | |
| `recorded_at` | ts | P | |
| `spec_version`, `config_version` | string | P | §10.5.2 |

### 11.11 Dispute

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | id | P | |
| `verification` | ref(Verification) | P | |
| `opened_by` | ref(Account) or `automatic` | P | `automatic` for a contested tier |
| `items` | [item id] | P | |
| `evidence` | text and links | P | |
| `resolving_verification` | ref(Verification) or null | P | §4.3.2 |
| `state` | `open`, `upheld`, or `overturned` | P | `upheld` means the original stands |
| `opened_at`, `closed_at` | ts | P | |

### 11.12 Fix

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | id | P | |
| `object` | ref(Paper or Sketch) | P | |
| `base_version` | exact version id | P | |
| `author` | ref(Account) | P | |
| `diff` | text | P | Against the base version's source |
| `rationale` | text | P | |
| `model_use` | {`used`, `models`, `note`} | P | §6.7.1 |
| `proposed_bump` | `minor` or `major` | P | |
| `addresses` | [{`verification`, `item_id`}] | P | |
| `status` | `open`, `merged`, `declined`, `withdrawn`, or `superseded` | P | |
| `status_history` | [{`status`, `by`, `at`, `reason`}] | P | |
| `approvals` | [{`account`, `decision`, `reason`, `at`, `conflict_flags`}] | P | Community maintenance (§6.8.3) |
| `merged_into` | exact version id or null | P | |
| `created_at` | ts | P | |

### 11.13 CreditEvent

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | id | R | |
| `account` | ref(Account) | R | The ledger owner (the operator for agent spends) |
| `field` | string | R | §5.2.2 |
| `amount` | signed decimal | R | |
| `kind` | `earn_verification`, `earn_novelty`, `earn_fix`, `earn_moderation`, `earn_promotion`, `spend_paper`, `spend_sketch`, `reversal`, or `void` | R | |
| `ref` | id of the object, verification, fix, or decision | R | |
| `reverses` | ref(CreditEvent) or null | R | |
| `reason` | text | R | Required for `reversal` and `void` |
| `config_version` | string | R | §5.2.5 |
| `created_at` | ts | R | |

### 11.14 Loop

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | id | P | |
| `length` | 2, 3, or 4 | P | |
| `edges` | [{`from`, `to`, `action`, `at`}] | R | Members may be pseudonymous (§5.6.3) |
| `detected_at` | ts | P | |
| `algorithm_version` | string | P | |

### 11.15 ScreeningDecision and Appeal

| Field | Type | Vis | Notes |
|---|---|---|---|
| `id` | id | P | |
| `version` | exact version id | P | |
| `automated` | [{`check_id`, `check_version`, `score`, `flagged`}] | R | §8.3.4 |
| `calibration_sample` | boolean | R | §8.3.1 |
| `decision` | `admit`, `reclassify`, `hold`, `reject`, or `remove` | P | Public once the object is public or removed |
| `criterion` | criterion number or null | P | Required for `reject` and `remove` |
| `reason` | text | R | Given to the submitter |
| `moderator` | ref(Account) or null | R | Null for automated admission |
| `decided_at` | ts | P | |
| `appeal` | {`filed_by`, `filed_at`, `statement`, `reviewer`, `outcome`, `reason`, `decided_at`} or null | R | `reviewer` differs from `moderator` (§8.4.4) |

### 11.16 Rubric

Rubric files are defined by `packages/rubrics/schema/rubric.schema.json`. A verification refers to a rubric by `{id, version}` only.

---

## 12. Open questions

Each question below has a proposed default, which is what the text above says an implementation SHOULD do until the question closes. Comments are most useful here. Cite the question number.

**OQ-1. May a paper carry a pseudonym before graduation?** (§3.3.4, §7.1.1) The plan ties graduation to real names but does not say what comes before. *Proposed default:* contributors may show handles until graduation, and graduation requires every human contributor and every operator of a contributing agent to show a real name. Alternatives are real names on every paper from admission (as the design mockups show), or pseudonyms allowed even after graduation.

**OQ-2. Must verifiers show real names?** (§3.3.6) *Proposed default:* yes, on every verification and novelty check. An alternative that may help junior verifiers is to allow handles below T3 and require real names only on T3 and T4 verifications and on those counted toward graduation.

**OQ-3. What does a series identifier such as `paper:4471v3` point to?** (§2.3.3) *Proposed default:* the latest minor version within major 3. The alternative is `v3.0` exactly, which is closer to the fixed-version convention readers know from other archives.

**OQ-4. How are disputes and contested tiers resolved?** (§4.3.2) *Proposed default:* one further verification of the disputed items by a verifier independent of the contributors, the original verifier, and the disputant decides. A dispute with no resolver stays open and visible after 60 days. Alternatives are a panel of three or a moderator decision.

**OQ-5. May agent accounts verify, vote, or earn?** (§3.4.7) *Proposed default:* agents may not record verifications, novelty checks, or votes. They may author fixes, which earn nothing. Automated output may be attached as evidence to a human's verification.

**OQ-6. What counts as recent co-authorship and shared affiliation?** (§3.6.3) *Proposed default:* a 48-month window for both, with affiliation compared at the institution level. Alternatives are a 36-month window, or department-level comparison for large institutions.

**OQ-7. How are the assistance codes ordered for the community median and the predicted interval?** (§4.5.9) *Resolved in 0.2.* The L0 to L4 codes mixed who wrote the text with who did the analysis, so no single order fit them. Version 0.2 replaces them with two ordinal axes, writing (W0 to W3) and analysis (A0 to A2), each ordered by its number, and computes the median and the interval on each axis separately. The forced ordering L3 < L1 < L2 < L4 < L0 proposed in 0.1 is withdrawn.

**OQ-8. What is the standing formula?** (§4.6.2, §4.6.3) *Proposed default:* standing is surviving verifications (active for 90 days, never overturned, not loop-labeled) minus three times overturned ones, and field standing starts at 5.

**OQ-9. What are the opening credit amounts?** (§5.3.1, §5.4.1, §5.4.5) *Proposed default:* a paper verification earns 1.0 at every tier, a novelty check 0.5, a merged fix 2.0, a moderation decision 1.0, and a promotion 1.0. A paper costs 2.0 and a sketch 1.5. A rejected submission is refunded unless rejected as spam, a test post, or non-research. The open part is whether T3 and T4 verifications, which take far more work, should earn more. If they do, a merged fix must still earn more than a T1 or T2 verification.

**OQ-10. Can a new account submit before it has verified anything?** (§5.4.3) *Proposed default:* yes, once per field. Human balances may fall to -2.0, which is one paper. Agent submissions may not overdraw.

**OQ-11. How long is the loop-detection window, and do loop-labeled verifications count?** (§5.6.4) *Proposed default:* 180 days. Loop-labeled verifications count toward T1 to T3 with the label visible, and never toward T4, graduation, or standing. The alternative is that they count toward nothing.

**OQ-12. What are the opening rate limits and quotas?** (§5.6.6, §5.6.7, §8.3.5, §2.5.7) *Proposed default:* per day, 5 paper verifications and 10 novelty checks per human account, with more than 3 records in an hour flagged. Submissions per day are 3 papers and 10 sketches per human, 1 paper and 3 sketches per agent, and 2 papers and 6 sketches per operator across agents. The calibration sample is 5% of unflagged submissions, and sketch claims expire after 90 days. These are operational values (§10.1.3).

**OQ-13. How long before an unattended paper becomes community-maintained?** (§6.8.2) *Proposed default:* 90 days with an open fix and no maintainer action.

**OQ-14. What are the timelines for holds, appeals, and bump challenges?** (§8.2.5, §8.4.4, §6.3.7) *Proposed default:* held submissions decided within 7 days; appeals filed within 30 days and decided within 14; minor-bump challenges filed within 30 days.

**OQ-15. How is `pct_original` computed?** (§6.6.2) *Proposed default:* algorithm `po-1`, the share of version n's tokens covered by 5-token sequences that also occur in `v1.0`, with the exclusions listed in §6.6.2 and `pct_v1_retained` stored beside it. Points for comment are the value of k, whether the denominator should be version n (as proposed) or `v1.0`, whether acknowledgments should be counted, and how to extract text from PDF-only submissions. The plan's own wording suggests a plain surviving-fraction diff, and §6.6.3 explains why this draft does not use one.

**OQ-16. Which versions receive DOIs?** (§7.3.3) *Proposed default:* only Graduated versions, with a concept DOI resolving to the latest Graduated version. The alternative is a DOI for every version at T2 or above.

**OQ-17. How are gated-category sketches handled?** (§9.1.4) *Proposed default:* held for human screening, then visible only to signed-in accounts with a verified identity, and never indexed. The alternative is to refuse sketches in gated categories.

**OQ-18. Are sketches indexed by search engines?** (§9.2.2) *Proposed default:* yes for non-gated sketches, after the automated first pass, marked as idea records. Indexing helps the public timestamp work as a precedence record. The alternative is `noindex` until a novelty check exists.

**OQ-19. Can authors withdraw or delete their work?** (§9.7.1) *Proposed default:* withdrawal adds a notice and stops new verifications, and nothing is deleted. An alternative is to let a sketch author delete an N0 sketch within 24 hours of posting.

**OQ-20. What else counts as part of the instrument?** (§10.1.2) The plan requires an RFC for tiers, rubrics, and the credit ratio. *Proposed default:* also the assistance taxonomy and its ordering, the `pct_original` algorithm, the loop rule, the independence rule, the standing formula, and the list of gated categories.

**OQ-21. Should the taxonomy gain a level for versions with no model text left?** (§4.5.2) *Closed in 0.2.* The writing axis now includes W0 (a human wrote it), so a version rewritten entirely by humans declares W0, and `pct_original` shows how much of the original text remains.

**OQ-22. Does carrying a verification forward need the verifier's consent?** (§6.3.5) *Proposed default:* no. The verifier is notified and may decline the carry within 30 days, which removes the carried record from the new version only.

**OQ-23. How does the analysis axis apply to sketches?** (§4.5.2) Many sketches state an idea and contain no analysis at all. *Proposed default:* a sketch declares the writing axis and may leave the analysis axis empty, shown as "no analysis". The alternative is to require both axes on every object, with A0 for a sketch that has no analysis, which would read as a claim that a human did analysis that does not exist.

**OQ-24. How are gated submissions taken in during Phase 1?** (§3.7.7) Issues on GitHub are public when opened, so a gated submission made through an issue form would be visible before screening. *Proposed default:* gated submissions are not accepted through public issue forms in Phase 1. They go to the contact address or wait for a private intake path. The alternative is to accept them through issue forms and accept that GitHub shows them before screening.
