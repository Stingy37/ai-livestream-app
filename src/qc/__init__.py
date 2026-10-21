"""Quality Control team. Public interface: ``WebsiteScorer``, ``ScriptHarness``, ``ScriptScorer``
(see the Team Interface Contract). ``qc.simple`` is the contradiction engine both parts are built on.
"""

from qc.quality_control import ScriptHarness, ScriptScorer, WebsiteScorer

__all__ = ["ScriptHarness", "ScriptScorer", "WebsiteScorer"]
