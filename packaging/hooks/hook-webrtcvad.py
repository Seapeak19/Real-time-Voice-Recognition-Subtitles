"""Local hook for webrtcvad-wheels.

The upstream contrib hook calls ``copy_metadata('webrtcvad')``, but the wheel
distribution is named ``webrtcvad-wheels``, so no metadata exists.  The C
extension itself is discovered normally; this hook intentionally does nothing.
"""
