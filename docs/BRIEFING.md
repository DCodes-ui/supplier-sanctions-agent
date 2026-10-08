# Briefing

A supplier is screened by name, country, and an optional registration number. The result is one of three decisions, tied to the list snapshot that was active at the time.

- **clear.** No listed name scored 0.72 or higher, and the country is not on the elevated-risk list. Proceed and record the screening.
- **review.** A person should look before anyone onboards or pays. The name is similar, the name is shared by many listed people, the countries conflict, or the country is North Korea, Iran, Syria, or Cuba with no list hit.
- **likely_hit.** Stop. The registration number matches one listed record, or the name scores at least 0.90 and a second fact supports it.

A person still decides. The tool does not onboard, pay, or block a supplier by itself.

## Data used:

Three files are downloaded. The EU Financial Sanctions Files and the OFAC SDN list are the official sources. The OpenSanctions consolidated sanctions file is included because this project is not used commercially. OpenSanctions allows that bulk file without a licence only for non-commercial use.

UN, UK, and the Baltic national lists are inside the OpenSanctions file. They are not separate downloads. Rows that repeat the official EU or OFAC SDN lists are skipped, so those parties are not stored twice.

The loaded snapshot is `20261005T181636Z`: 6,241 EU records, 19,488 OFAC SDN records, and 49,416 OpenSanctions records. A decision stores that snapshot id. A later download does not overwrite the raw files of an older snapshot.

## Matching:

The typed name is folded to a comparable form: lower case, Cyrillic to Latin, diacritics removed, punctuation removed, and a trailing legal form such as UAB or Ltd dropped. The original spelling stays in the evidence. An exact registration number is a likely hit on its own. Otherwise the search keeps names that share a distinctive word, scores them from 0 to 1, and drops anything below 0.72. From 0.72 up to 0.90 the result stays review. At 0.90 or above it becomes a likely hit only with a second fact, such as the country, or a rare name at 0.96 or above. A name shared by 8 or more listed people never becomes a likely hit without an exact registration number. "Mohammed Ali" is the kind of name that rule is there for.

## LLM:

Grok 4.7 is called through the xAI API, and only after the matcher has a shortlist. It sees the supplier and at most five candidates. It may lower a likely hit to review. It may not raise a review candidate to a likely hit, and it may not name a record that was not on the shortlist. The answer has to match a fixed JSON schema. One bad answer is sent back for a repair. If that also fails, or if there is no API key, the score rules stand. A failed model call is stored as `fallback`, so it is visible that a script checked the result.

## Security:

The API key lives in the environment, not in the repository. The model does not receive the sanctions lists. It receives one supplier and five candidates. Raw downloads are written once, under `data/snapshots/`, and are not overwritten. The active snapshot changes only after EU, OFAC SDN, and OpenSanctions have all been stored and indexed.

We obviously use a third party API, so regardless of the amount of data we send, it is probably fair to assume the data will get used by the third-party.

## Evaluation:

Fifty cases were scored with the rules only.


| Check                                                  | Target | Result       |
| ------------------------------------------------------ | ------ | ------------ |
| Real listed names flagged as review or likely_hit      | 0.98   | 0.97 (37/38) |
| likely_hit precision on cases that expect a likely hit | 0.95   | 1.00 (17/17) |
| Common names returned as likely_hit                    | 0      | 0            |


The one miss is a real listed name with the middle word removed: "10th Institute of China Electronic Technology Group Corporation (CETC)". It scored under 0.72 and came back clear. The next threshold to change, if that case should be caught, is `discard_below` in `screener/config/thresholds.yaml`, not the 0.90 line.