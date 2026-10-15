# Spot check: how to fill in `keyword_spot_check.csv`

Each row has a phrase and the sentence it comes from. For each row decide:

1. **your_dimension**: which of the domain's dimensions the phrase bears on, or `none` if it is generic and says nothing specific about any of them.
2. **your_direction**: `raises` if the phrase points toward the dimension's positive end, `lowers` if toward its negative end. Leave blank for `none`.

Judge the phrase as used in its sentence. Do not look at `keyword_benchmark.json` first; the point is an independent opinion.

When done: `python -m policyswarm.tools.eval_suggest --check-spot-check tests/data/keyword_spot_check.csv`

## ai_governance

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `deployment_cap` | How freely AI systems may be put on the market and used. | deployment is permissive: few limits on releasing and using AI systems | deployment is restricted: bans, licences and approvals before release |
| `transparency` | What providers must reveal about their systems and data. | strict disclosure and explainability duties | little or no duty to disclose; secrecy is allowed |
| `enforcement` | How breaches of the rules are punished. | strong penalties and powers to compel compliance | weak, delayed or no penalties |
| `audit_intensity` | How closely systems are checked and monitored. | frequent, independent audits and monitoring | little checking; providers assess themselves |

## healthcare

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `access_restriction` | How far the policy limits patients' access to treatments and services. | severe restrictions: authorisations, referrals and gatekeeping before care | open access: patients reach care without gatekeeping |
| `cost_sharing` | How much of the cost of care patients pay themselves. | high patient burden: deductibles, copayments and charges | care is free or nearly free to the patient |
| `provider_regulation` | The regulatory burden on providers and insurers. | extensive licensing, reporting and compliance duties | minimal regulation of providers |
| `coverage_mandate` | How much care plans are required to cover. | comprehensive mandated benefits with few exclusions | bare-bones coverage with many exclusions permitted |

## data_privacy

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `consent_requirement` | What kind of agreement is needed before personal data is used. | strict: explicit, informed, opt-in consent is required | loose: implied consent, opt-out or no consent is enough |
| `data_minimisation` | How far collection, reuse and retention of data are limited. | strict limits on what is collected, how long it is kept and what it is reused for | data may be collected in bulk, kept and reused freely |
| `individual_rights` | What individuals can demand regarding their own data. | strong rights to access, correct, delete and move their data | few rights; requests can be refused or charged for |
| `enforcement` | How breaches of the rules are punished. | strong penalties and regulator powers | weak, advisory or no penalties |

## climate

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `carbon_pricing` | Whether and how much emitters pay for their emissions. | a high, broad price on emissions | low or no carbon price; exemptions and free permits |
| `emission_standards` | Binding limits and technical requirements on polluters and products. | strict mandatory limits and standards | lax, voluntary or relaxed standards |
| `green_subsidies` | Public financial support for clean technology. | generous public funding for clean technology | little or no public support; left to the market |
| `fossil_phaseout` | Whether fossil fuel use and production are being wound down. | rapid phase-out of fossil fuels | continued or expanded fossil fuel production and use |
