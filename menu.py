import nuke
import bvfx_furytools
import logging
import os

log = logging.getLogger(__name__)
log.info("Loading %s " % os.path.abspath(__file__))

def bvfxsignature():
    thenode = nuke.thisNode()
    if "RotoFury" in thenode.name() or "TrackerFury" in thenode.name():
    	bvfx_furytools.signature(thenode)

nuke.addOnCreate(bvfxsignature, nodeClass="Group")