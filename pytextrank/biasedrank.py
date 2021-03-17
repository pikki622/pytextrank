"""
Implements the *BiasedTextrank* algorithm.
"""

from spacy.tokens import Doc, Token  # type: ignore
import typing

from .base import BaseTextRankFactory, BaseTextRank, Lemma, Phrase


class BiasedTextRankFactory (BaseTextRankFactory):
    """
A factory class that provides the document with its instance of
`BiasedTextRank`
    """

    def __call__ (
        self,
        doc: Doc,
        ) -> Doc:
        """
Set the extension attributes on a `spaCy` [`Doc`](https://spacy.io/api/doc)
document to create a *pipeline component* for `BiasedTextRank` as
a stateful component, invoked when the document gets processed.

See: <https://spacy.io/usage/processing-pipelines#pipelines>

    doc:
a document container, providing the annotations produced by earlier stages of the `spaCy` pipeline
        """
        Doc.set_extension("textrank", force=True, default=None)
        Doc.set_extension("phrases", force=True, default=[])

        doc._.textrank = BiasedTextRank(
            doc,
            edge_weight = self.edge_weight,
            pos_kept = self.pos_kept,
            token_lookback = self.token_lookback,
            scrubber = self.scrubber,
            stopwords = self.stopwords,
            )

        doc._.phrases = doc._.textrank.calc_textrank()
        return doc


class BiasedTextRank (BaseTextRank):
    """
Implements the *Biased TextRank* algorithm described by
[[kazemi2011corr]](https://derwen.ai/docs/ptr/biblio/#kazemi2011corr),
deployed as a `spaCy` pipeline component.

This class does not get called directly; instantiate its factory
instead.
    """

    _NODE_BIAS: float = 1.0


    def _get_node_bias (
        self,
        token: Token,
        ) -> float:
        """
Assign the bias to use, where focus nodes get the preset bias and
other nodes get the default (`1.0`) value.

    token:
`spaCy` token to use for lookup in the focus set

    returns:
bias to apply for the *node weight*
        """
        if token.text in self.focus_tokens:
            return self.node_bias

        if token.lemma_ in self.focus_tokens:
            return self.node_bias

        return self._NODE_BIAS


    def get_personalization (
        self,
        ) -> typing.Optional[typing.Dict[Lemma, float]]:
        """
Get the *node weights* for initializing the use of the
[*Personalized PageRank*](https://derwen.ai/docs/ptr/glossary/#personalized-pagerank)
algorithm.

    returns:
biased restart probabilities to use in the *PageRank* algorithm.
        """
        # TODO: lookup bias based on (lemma, pos) instead, similar to *PositionRank*?
        weighted_nodes: typing.Dict[Lemma, float] = {
            Lemma(token.lemma_, token.pos_): self._get_node_bias(token)
            for token in self.doc
            if token.pos_ in self.pos_kept
        }

        # normalize weights
        total_weight = sum(weighted_nodes.values())

        if total_weight == 0.0:
            return None

        normalized_weighted_nodes: typing.Dict[Lemma, float] = {
            lemma : weight / total_weight
            for lemma, weight in weighted_nodes.items()
            }

        return normalized_weighted_nodes


    def change_focus (
        self,
        focus: str = None,
        bias: float = _NODE_BIAS
        ) -> typing.List[Phrase]:
        """
Re-runs the *Biased TextRank* algorithm with the given focus.
This approach allows an applicatino to "change focus" without
re-running the entire pipeline.

    focus:
optional text (string) with space-delimited tokens to use for the *focus set*; defaults to `None`

    bias:
optional bias for *node weight* values on tokens found within the *focus set*; defaults to `1.0`

    returns:
list of ranked phrases, in descending order
        """
        # update the focus parameters
        if focus:
            self.focus_tokens = set(focus.lower().split(" "))
        else:
            self.focus_tokens = set()

        self.node_bias = bias

        # update the textrank phrase extraction
        return self.calc_textrank()