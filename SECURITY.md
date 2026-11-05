# Security and sensitive-data handling

This toolkit is local and read-only with respect to its declared inputs. It does
not provide clinical-system authentication, authorization, encryption, signed
audit trails, or electronic signatures. Deploy only within an appropriately
controlled environment.

Do not report vulnerabilities by opening a public issue containing clinical
data. Use the repository owner's approved private reporting channel. Remove
participant records, reviewer text, local paths, credentials, and production
identifiers from any reproduction; a fictional example is preferred.

Input safeguards include explicit files/sheets, formula rejection in canonical
XLSX inputs, rejection of XML DTD/entity declarations, bounded individual input
and archive-member sizes, no ZIP extraction, escaped report HTML, and
spreadsheet-safe report cells. These reduce specific risks; they do not make
untrusted files generally safe or replace organizational malware scanning.

Review reports may contain the same sensitive values as the source. Keep them
out of public repositories and retain them under approved access/retention
policies. The built-in repository scan is a limited release aid, not a complete
privacy, security, or licensing review.

