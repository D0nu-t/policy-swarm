# Spot check: how to fill in `keyword_training_spot_check.csv`

Same method as the benchmark sheet. For each row decide:

1. **your_dimension**: which of the domain's dimensions the phrase bears on, or `none`.
2. **your_direction**: `raises` (toward the positive end) or `lowers`; blank for `none`.

Do not look at `keyword_training.json` first. When done:

`python -m policyswarm.tools.eval_suggest --labelled tests/data/keyword_training.json --check-spot-check tests/data/keyword_training_spot_check.csv`

## tax

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `progressivity` | How the income tax burden is spread across earners. | higher earners pay a larger share | flat or regressive: the same or lower rates for high earners |
| `corporate_taxation` | How heavily companies are taxed. | higher taxes on company profits | lower company taxes and more reliefs |
| `consumption_taxes` | Taxes on spending such as sales tax, VAT and excise. | higher taxes on purchases | lower or no taxes on purchases |
| `wealth_taxation` | Taxes on assets, inheritance and property. | wealth, estates and property are taxed | assets and inheritances go untaxed |
| `tax_enforcement` | How strictly evasion and avoidance are pursued. | strict audits and penalties for evasion | lenient treatment of evasion |

## immigration

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `admission_levels` | How many people are allowed to come. | more people admitted; wider legal routes | fewer admitted; caps and closed routes |
| `border_control` | How strictly borders are policed and removals carried out. | strict border policing, detention and removals | light enforcement and few removals |
| `migrant_rights` | The rights and services available to migrants. | broad access to work, services and legal protection | restricted access to work and services |
| `path_to_citizenship` | How easily residents can become citizens. | a short, open route to citizenship | a long or closed route to citizenship |

## education

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `school_funding` | How much public money goes to schools and students. | more public funding per pupil | funding cuts and higher fees |
| `standardised_accountability` | How far schools are judged by tests and inspections. | heavy testing, inspection and league tables | little testing; schools are trusted |
| `school_choice` | How far families can choose, and providers compete. | wide choice: charters, vouchers and private options | pupils attend their assigned public school |

## housing

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `rent_regulation` | How far rents and evictions are controlled. | strong rent controls and tenant protection | rents and evictions left to landlords |
| `public_housing` | The state's role in providing homes. | the state builds and funds social housing | social housing is sold off or unfunded |
| `planning_liberalisation` | How easy it is to get permission to build. | loose planning rules; building is easy | tight planning rules; building is hard |
| `homeownership_support` | Help for people buying a home. | subsidies and relief for buyers | no help for buyers |
| `property_speculation_curbs` | Measures against empty homes and speculative buying. | taxes and bans on speculation and vacant homes | no limits on investment buying |

## labour

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `minimum_wage` | The legal wage floor. | a higher and broader minimum wage | a low, frozen or absent minimum wage |
| `job_security` | How hard it is to dismiss workers. | strong protection against dismissal | easy hiring and firing |
| `union_power` | The legal strength of trade unions. | strong collective bargaining and strike rights | restricted unions and strikes |
| `working_time` | Limits on hours and rights to leave. | shorter hours and generous leave | long hours and little leave |
| `gig_worker_status` | Whether platform and casual workers count as employees. | gig workers get employee rights | gig workers are independent contractors |
| `unemployment_support` | Income support for people out of work. | generous, long-lasting benefits | low, short or conditional benefits |

## trade

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `tariff_protection` | Taxes and limits on imported goods. | high tariffs and quotas protecting domestic producers | low tariffs and open markets |
| `standards_in_agreements` | Whether trade deals carry labour and environmental conditions. | binding labour and environmental conditions in deals | deals without such conditions |
| `export_promotion` | State support for exporters. | active state support for exporters | no state support for exporters |

## energy_markets

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `price_regulation` | Whether the state sets or caps energy prices. | prices are capped or set by the state | prices are set by the market |
| `public_ownership` | Who owns generators, grids and suppliers. | the state owns energy assets | energy assets are privately owned |
| `market_competition` | How open the sector is to rival firms. | many competing firms; unbundled monopolies | protected monopolies and barriers to entry |
| `supply_security` | Measures to guarantee that supply does not fail. | reserves, capacity payments and stockpiles | no reserves; reliance on spot supply |

## policing

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `police_powers` | What officers are allowed to do. | wide powers to stop, search and detain | narrow powers with strict limits |
| `sentencing_severity` | How harshly offenders are punished. | long, mandatory sentences | short sentences and alternatives to prison |
| `police_oversight` | How police conduct is scrutinised. | strong independent scrutiny of police | little outside scrutiny |
| `surveillance` | State monitoring of the public. | extensive monitoring and data retention | tight limits on monitoring |
| `prevention_spending` | Investment in social programmes to prevent crime. | more spending on prevention and rehabilitation | prevention programmes are cut |

## food_safety

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `safety_standards` | How strict the rules on what may be sold are. | strict limits and bans on risky ingredients and practices | permissive rules on what may be sold |
| `labelling_requirements` | What must be disclosed to consumers. | detailed mandatory labels | few or voluntary labels |
| `inspection_regime` | How often and how thoroughly producers are checked. | frequent official inspections and testing | few inspections; firms check themselves |

## telecoms

| Dimension | About | Positive end (raises) | Negative end (lowers) |
|---|---|---|---|
| `net_neutrality` | Whether networks must treat all traffic equally. | all traffic must be treated equally | providers may prioritise or block traffic |
| `universal_service` | Whether everyone is guaranteed a connection. | a guaranteed affordable connection for all | no guarantee; coverage left to the market |
| `content_moderation_duties` | What platforms must do about harmful content. | platforms must remove harmful content | platforms have no such duties |
| `spectrum_liberalisation` | How radio spectrum is allocated. | spectrum is auctioned and tradable | spectrum is assigned by the state |
| `market_concentration_limits` | Limits on dominant operators. | strict limits on dominant operators and mergers | consolidation is allowed |
| `network_security_rules` | Security requirements on network equipment and operators. | strict security rules and vendor bans | no special security rules |
