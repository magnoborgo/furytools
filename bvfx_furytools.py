import nuke
import logging
import os
import nuke.rotopaint as rp
import _curvelib as cl
import _curveknob as ck

__version__ = "1.0.0"
__author__ = "Magno Borgo"
__creation__ = "Sep 13 2023"
__date__ = "Oct 14 2023"
__web__ = "www.boundaryvfx.com"

log = logging.getLogger(__name__)
log.info("Loading %s " % os.path.abspath(__file__))


def signature(thenode):
    """Updates the signature on the gizmo using this script variables

    Args:
        thenode (Node): the Node calling the function
    """
    name = "RotoFury" if "RotoFury" in thenode.name() else "TrackerFury"
    name += " - Revenge of the Motion Vectors"
    header = '''<span style="color:#aaa;font-family:sans-serif;font-size:8pt">'''
    extratext = '''<br>by <a href="https://github.com/magnoborgo/" style="color:#aaa">Magno Borgo</a>\nBoundary Visual Effects</span>'''
    version = "<br>v " + str(__version__) + " created " + \
        __creation__ + ", updated " + __date__
    try:
        thenode["bvfxsignature"].setValue(name+header+version + extratext)
        thenode["fRangeS"].setValue(nuke.Root()["first_frame"].getValue())
        thenode["fRangeE"].setValue(nuke.Root()["last_frame"].getValue())
    except Exception:
        pass


def trackerGrid(thenode):
    """Created a grid of trackers

    Args:
        thenode (Node): the Node calling the function

    Raises:
        Exception: Checks if the node connected is Tracker4
    """
    inputNode = thenode.input(0)  # roto or tracker input

    nodeWidth = thenode.width()
    nodeHeight = thenode.height()
    columns = int(thenode['trkgridX'].getValue()+1)
    rows = int(thenode['trkgridY'].getValue()+1)

    if inputNode.Class() != "Tracker4":
        raise Exception("Please attach a Tracker4 to TrackerNode input")

    numColumns = 31
    Trk4_parameters = ["enable", "name", "track_x", "track_y", "offset_x", "offset_y", "T", "R", "S", "error", "error_min",
                       "error_max", "pattern_x", "pattern_y", "pattern_r", "pattern_t",  "search_x", "search_y", "search_r", "search_t"]

    trackerNode = inputNode
    numTracks = 0
    # tracker4 control panel must be open or script wont work
    inputNode.showControlPanel()

    for _ in range(1, 1000):
        check = nuke.tcl(
            "value {0}.tracks.{1}.track_x".format(trackerNode.name(), _))
        if check == '1':
            numTracks = _ - 1
            break
    trker = 0
    for c in range(1, columns):
        x = (nodeWidth/columns)*c
        for r in range(1, rows):
            trackerNode["add_track"].execute()
            y = (nodeHeight/rows)*r
            trackerNode['tracks'].setValueAt(
                x, nuke.frame(), numColumns*(trker+numTracks) + Trk4_parameters.index("track_x"))
            trackerNode['tracks'].setValueAt(
                y, nuke.frame(), numColumns*(trker+numTracks) + Trk4_parameters.index("track_y"))
            trker += 1


def roto_walker(nodeRoot, shapelist=[]):
    """Walks recursively on the roto tree and return a list of shapes and strokes

    Args:
        nodeRoot (TYPE): Description
        shapelist (list, optional): list to hold the objects

    Returns:
        list: with all the shapes/strokes

    """
    for i in nodeRoot:
        if isinstance(i, rp.Shape) or isinstance(i, ck.Stroke):
            shapelist.append(i)
        else:
            roto_walker(i, shapelist)
    return shapelist


def sampleInRangecv(node, x, y, f):
    """ samples the image with a curve tool

    Args:
        node (Node): a curvetool node
        x (float): pixel xpos
        y (float): pyxel ypos
        f (time): frame to sample

    Returns:
        float: u,v values
    """
    r = x+1
    t = y+1

    node["ROI"].fromDict({'y': y, 'x': x, 'r': r, 't': t})
    nuke.execute(node, f, f)
    uv = node['intensitydata'].getValueAt(f)

    return uv[0], uv[1]


def main(thenode, furytool, mode="default"):
    """Main function for both rotofury and trackerfury since they share a lot of the same code

    Args:
        thenode (Node): the Node that is requesting this execution
        furytool (str): "roto" or "tracker"
        mode (str, optional):   "default" comes from the "execute" button, to run frameranges
                                "nextnframes", evaluate forward the next n frames (execution interval)
                                "previousnframes", evaluate backward the previous n frames (execution interval)

    Raises:
        Exception: Description
    """
    inputNode = thenode.input(0)  # roto or tracker input
    execution_type = thenode["execution_type"].getValue()

    if furytool == "roto":
        if inputNode.Class() not in ("Roto", "RotoPaint"):
            raise Exception(
                "Please attach a Roto or Rotopaint node to RotoNode input")
        rotoCurves = inputNode['curves']
        rotoRoot = rotoCurves.rootLayer
        if len(rotoRoot) == 0:
            raise Exception("Roto node empty, create a shape")
    elif furytool == "tracker":  # its a tracker
        if inputNode.Class() != "Tracker4":
            raise Exception("Please attach a Tracker4 to TrackerNode input")
        numColumns = 31
        Trk4_parameters = ["enable", "name", "track_x", "track_y", "offset_x", "offset_y", "T", "R", "S", "error", "error_min",
                           "error_max", "pattern_x", "pattern_y", "pattern_r", "pattern_t",  "search_x", "search_y", "search_r", "search_t"]
        trackerNode = inputNode  # nuke.toNode("TrackerFury")
        nodeTracks = trackerNode['tracks']
        if trackerNode['selected_tracks'].value() == "" and execution_type == 0.0:
            raise Exception(
                "Please select some trackers on " + inputNode.name())

    else:
        raise Exception("Wrong furytool setting")

    # variables setup
    update_sampling = int(thenode["updateInterval"].getValue())

    if mode == "default":
        start_frame = int(thenode["fRangeS"].getValue())
        end_frame = int(thenode["fRangeE"].getValue())
    elif mode == "nextnframes":
        start_frame = int(nuke.frame())
        end_frame = int(nuke.frame()) + update_sampling
    elif mode == "previousnframes":
        start_frame = int(nuke.frame())
        end_frame = int(nuke.frame()) - update_sampling

    key_only = int(thenode["keyframe"].getValue())
    # access node inside group
    target = nuke.toNode(thenode.name()+".Shuffle_mv")
    curve_tool = nuke.toNode(thenode.name()+'.ct')
    if furytool == "roto":
        if execution_type == 0.0:  # selected
            idxs = [point.center for shape in rotoCurves.getSelected()
                    for point in shape if isinstance(shape, rp.Shape)]
        elif execution_type == 1.0:  # all
            shapes = roto_walker(rotoRoot)
            idxs = [point.center for shape in shapes for point in shape if isinstance(
                shape, rp.Shape)]
            # print(idxs)
    elif furytool == "tracker":
        if execution_type == 0.0:  # selected
            idxs = [int(x)
                    for x in trackerNode['selected_tracks'].value().split(",")]
        elif execution_type == 1.0:  # all
            # ===============================================================
            # find the amount of trackers inside this Tracker4 mess
            numTracks = 0
            for _ in range(1, 1000):
                check = nuke.tcl(
                    "value {0}.tracks.{1}.track_x".format(trackerNode.name(), _))
                if check == '1':
                    numTracks = _ - 1
                    break
            idxs = range(numTracks)

    if len(idxs) == 0 and furytool == "roto":
        raise Exception("Please select some shapes!")
    elif len(idxs) == 0 and furytool == "tracker":
        raise Exception("Please select trackers on %s" + inputNode.name())
    else:
        intensity_knob = curve_tool['intensitydata']
        intensity_knob.clearAnimated()
        intensity_knob.setAnimated()

        progressframes = (end_frame-start_frame)+1 if (end_frame >=
                                                       start_frame) else (start_frame-end_frame)+1
        count = 1
        trackParams = {}
        if furytool == "roto":
            for point in idxs:
                x, y, z = point.getPosition(nuke.frame())
                trackParams[point] = {"x_pos": x, "y_pos": y, "x": x, "y": y}
            print(trackParams)
        elif furytool == "tracker":
            for trackIdx in idxs:
                x = nodeTracks.getValue(
                    numColumns*trackIdx + Trk4_parameters.index("track_x"))
                y = nodeTracks.getValue(
                    numColumns*trackIdx + Trk4_parameters.index("track_y"))
                trackParams[trackIdx] = {
                    "x_pos": x, "y_pos": y, "x": x, "y": y}

        frange = range(start_frame, end_frame+1) if (end_frame >=
                                                     start_frame) else range(start_frame, end_frame-1, -1)
        taskname = "RotoFury" if "RotoFury" in thenode.name() else "TrackerFury"
        task = nuke.ProgressTask(taskname)

        for frame in frange:

            # task progress stuff
            tprogress = int(count*100/progressframes)
            if tprogress % 1 == 0:  # update every x% otherwise progress task slows down processing
                task.setProgress(tprogress)
            if task.isCancelled():
                break
            # end task progress stuff

            nstep = update_sampling if key_only else 1

            for trackIdx in idxs:
                if task.isCancelled():
                    break
                # print(frame,trackParams[trackIdx])
                u, v = sampleInRangecv(
                    curve_tool, trackParams[trackIdx]["x"], trackParams[trackIdx]["y"], frame)
                if frame == start_frame:
                    updatex = trackParams[trackIdx]["x_pos"]
                    updatey = trackParams[trackIdx]["y_pos"]
                else:
                    if (end_frame >= start_frame):
                        updatex = trackParams[trackIdx]["x_pos"]+(u)
                        updatey = trackParams[trackIdx]["y_pos"]+(v)
                    else:  # going backwards
                        updatex = trackParams[trackIdx]["x_pos"]-(u)
                        updatey = trackParams[trackIdx]["y_pos"]-(v)

                if (frame - start_frame) % nstep == 0 or frame == end_frame:
                    if furytool == "roto":
                        trackIdx.addPositionKey(frame, (updatex, updatey))
                    elif furytool == "tracker":
                        nodeTracks.setValueAt(
                            updatex, frame, numColumns*trackIdx + Trk4_parameters.index("track_x"))
                        nodeTracks.setValueAt(
                            updatey, frame, numColumns*trackIdx + Trk4_parameters.index("track_y"))

                else:  # remove previous keys
                    if furytool == "roto":
                        trackIdx.removePositionKey(frame)
                    elif furytool == "tracker":
                        nodeTracks.removeKeyAt(
                            frame, numColumns*trackIdx + Trk4_parameters.index("track_x"))
                        nodeTracks.removeKeyAt(
                            frame, numColumns*trackIdx + Trk4_parameters.index("track_y"))
                trackParams[trackIdx]["x_pos"] = updatex
                trackParams[trackIdx]["y_pos"] = updatey
                if frame % update_sampling == 0:
                    #print("updating ref frame", frame )
                    # nuke.frame(frame)
                    # trackerNode["set_key_frame"].execute()
                    trackParams[trackIdx]["x"] = updatex
                    trackParams[trackIdx]["y"] = updatey
            count += 1

        if furytool == "roto":
            rotoCurves.changed()

        del(task)
        if mode in ("nextnframes", "previousnframes"):
            nuke.frame(end_frame)
        if furytool == "tracker":
            nuke.frame(end_frame)


if __name__ == '__main__':
    main()
