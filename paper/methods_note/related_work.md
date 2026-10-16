# Related work and novelty check (2026-10-15)

Searches covered metric choice in multidimensional bounded-confidence (BC) models, threshold calibration across metrics, angular and cosine BC models, and confidence-region size versus shape. Every entry below was opened or found through search. Nothing here is cited from memory. Entries marked *unread* were only seen in search results.

## Verdict
**Not done before, as far as these searches show.** Papers that change the distance or discordance function compare models at one shared threshold value. One of them explicitly notes that this changes the *size* of the region of agents that can interact as well as its *shape*, but none separates the two. The note's contribution is to separate them: match the coverage of neighbour pairs, report realised coverage, and observe that monotone-equivalent metrics collapse once matched.

## Papers to cite

| Paper | Why it matters | Status |
|---|---|---|
| Li, Luo & Chu, *Bounded-Confidence Models of Multidimensional Opinions with Topic-Weighted Discordance*, [arXiv 2502.00284](https://arxiv.org/abs/2502.00284); journal version [OSTI 3024680](https://www.osti.gov/biblio/3024680) | The closest prior work. Models are compared at a fixed confidence bound c. The authors note that "as we decrease ω, the area of the region of receptiveness increases" and attribute their less fragmented outcomes to "the larger size and non-square shape". Size and shape are confounded, and the paper says so. Their related-work section is a good map of non-Euclidean BCMs: L1 and L∞ variants, plus angular (Schweighofer et al.). Code: gitlab.com/graceli1/topic-weighted-BCMs. | read (sections 1–4) |
| Schweighofer, Garcia & Schweitzer (2020), *An agent-based model of multi-dimensional opinion dynamics and opinion alignment*, Chaos 30(9) 093139, [arXiv 2003.05929](https://arxiv.org/abs/2003.05929) | An angular-distance multidimensional model; the precedent for angular metrics. | abstract only |
| Lorenz, *Fostering consensus in multidimensional continuous opinion dynamics under bounded confidence*, [arXiv 0708.3172](https://arxiv.org/abs/0708.3172) | Euclidean distance as the standard multidimensional choice; other distances are "possible" further research. Contrasts cube and simplex opinion spaces, which relates to our unit-cube versus centred-cube point. | search snippet |
| Lorenz, *Continuous opinion dynamics of multidimensional allocation problems under bounded confidence*, [arXiv 0708.2923](https://arxiv.org/abs/0708.2923) | Dimension changes the chance of consensus, so the comparison must fix the dimension. | search snippet |
| Hegselmann & Krause (2002), *Opinion dynamics and bounded confidence*, [JASSS 5(3)/2](https://www.jasss.org/5/3/2.html) | The size of the confidence interval decides consensus versus camps (0.15 gives two camps, 0.25 consensus): the size effect that a mismatched threshold silently changes. | search snippet |
| Deffuant et al. (2000), *Mixing beliefs among interacting agents* | The pairwise update used in the minimal model. | *to fetch* |
| Bernardo et al., *Bounded confidence opinion dynamics: a survey*, [Automatica (2023)](https://www.sciencedirect.com/science/article/pii/S0005109823004661) | A survey reference for BC variants. | *unread* |
| Flache et al. (2017), *Models of social influence: towards the next frontiers*, [JASSS 20(4)/2](https://www.jasss.org/20/4/2.html) | A review placing BC within social-influence models. | *to fetch* |
| Zabarianska & Proskurnikov, multidimensional HK with general norms | Confidence sets as balls in a general norm. | *unread; locate* |

## Points to make in the text
1. The literature already treats the threshold as a free parameter tied to its distance function. The gap is a **procedure** for comparing distance functions fairly.
2. Li, Luo & Chu offer the cleanest illustration that the issue arises outside our own model: they say that region size changes with ω at fixed c. The note should cite this respectfully, as a case where coverage matching would separate their size and shape explanations. It must not be framed as an error on their part.
3. For uniform opinions in a unit cube, cosine distance is almost uninformative: every vector points into the positive orthant. The minimal model should show how often this arises.
