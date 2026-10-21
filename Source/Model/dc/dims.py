"""Single source for the rack / slot / server interface dimensions (metres). Plain Python (no bpy): rack.py,
server.py, servers/*, build_dc.py and the tests all read these.

Frame: Blender, centred on the block origin, X width, +Y = front = game Forward, Z up. "Slot-relative z" is measured
from a slot's floor (each slot is SLOT_H tall). The rack's geometry implements these numbers; the build measures the
built meshes back (build_report.json "geometry") and Tests/test_servers.py checks the couplings on those measurements.
"""
CELL = 0.25

# ---------------------------------------------------------------------------------------------------- the slot
SLOT_H = 0.25                 # slot pitch (one 6U server); a 12U server spans 2
SLOT_HALF_W = 0.25            # |x| of the slot side planes (2 cells): the rack's slide-rail plane
SLOT_HALF_D = 0.375           # |y| of the slot front / back planes (3 cells): the 19" rails' ear faces
SLOT_FRONT_Y = SLOT_HALF_D    # the slot front plane = the server's cell front

# ---------------------------------------------------------------------------------------------------- rack rails
RAIL_X = (0.25, 0.29)         # 19" rail angle (|x|): its ear face lies on y = +-SLOT_FRONT_Y
RAIL_DEPTH = 0.022            # rail angle depth behind the ear face
RAIL_HOLE_X = 0.262           # |x| of the square-hole column on the rail face
RAIL_HOLE_FIRST = 0.031       # slot-relative z of the first hole centre
RAIL_HOLE_PITCH = 0.0625      # 4 holes per slot: 0.031, 0.094, 0.156, 0.219
RAIL_HOLE_SIZE = 0.011
SLOT_TAB_Z = (0.106, 0.144)   # slot-relative z of the stencilled slot-number tab on the left front rail

# rack slide (outer member, C-section web on the slot plane), slot-relative z
RACK_SLIDE_Z = (0.075, 0.12)
RACK_SLIDE_BOLT_PROUD = 0.0015   # countersunk bolt heads stand this far into the slot
HALF_ROOF_T = 0.005           # the half rack's render-only roof sits this far inside its top slot

# ---------------------------------------------------------------------------------------------------- server fit
SIDE_LIMIT_X = SLOT_HALF_W - RACK_SLIDE_BOLT_PROUD - 0.0005   # 0.248: nothing of a server inside the slot past this
SERVER_TOP_GAP = HALF_ROOF_T + 0.001                          # 0.006: server top below its cell top
SERVER_BODY_X = 0.240         # body side plane
SERVER_SLIDE_X = (0.2405, SLOT_HALF_W - 0.003)               # server-side slide (inner member): to 0.247
SERVER_SLIDE_INSET = 0.005    # the server slide sits 5 mm inside the rack slide's height at each edge
SERVER_SLIDE_Z = (RACK_SLIDE_Z[0] + SERVER_SLIDE_INSET, RACK_SLIDE_Z[1] - SERVER_SLIDE_INSET)
EAR_GAP = 0.0005              # ear flange stands this far in front of the rail ear face
EAR_T = 0.006                 # ear flange thickness
EAR_X = (SERVER_BODY_X, RAIL_X[1] - 0.002)                   # the flange ends 2 mm short of the rail's outer edge
EAR_SCREW_HOLES = (0, 3)      # thumbscrews over the 1st and 4th hole of each slot
EAR_NOTCH = (SLOT_TAB_Z[1] - SLOT_TAB_Z[0]) / 2 + 0.007     # half height of the notch round the slot-number tab


def hole_offsets():
    """Slot-relative z of the rail's square-hole centres."""
    return [RAIL_HOLE_FIRST + k * RAIL_HOLE_PITCH for k in range(int(round(SLOT_H / RAIL_HOLE_PITCH)))]


def screw_offsets():
    """Slot-relative z of the ear thumbscrews (over the rail's holes)."""
    h = hole_offsets()
    return [h[i] for i in EAR_SCREW_HOLES]

RACK_SIDE_INSET = 0.001   # render mesh stays 1 mm inside the rack's side planes (flush racks: hairline gap, no z-fight)

# ---------------------------------------------------------------------------------------------------------------- doors
# Split perforated leaves hinged at the outer posts (APC style), re-derived for THIS rack (1.0 m wide, 1.25 m deep).
# The rack frame already stops 2.7 cm behind its front / back planes (KEEP_OUT: no mount points on the openings),
# and the posts' front faces sit on that plane (|y| = 0.598). The leaves live in the remaining layer
# |y| = DOOR_Y_BACK .. DOOR_Y_FRONT (2 mm clear of the frame, 2 mm inside the cell plane), so no post setback is
# needed (v2's 40 mm setback solved a rack whose posts reached the front plane). The hinge axis runs through the
# middle of that layer, DOOR_HINGE_INSET in from the side plane, and the knuckle barrels (radius = half the leaf
# thickness) are the outermost part of an open leaf: two flush racks keep 2 x (inset - knuckle) between their open
# leaves at any angle up to ~90 deg (dc/doors.py computes it on the built leaf hulls).
DOOR_HINGE_INSET = 0.026                      # hinge axis from the rack's side plane (v2: 26 mm)
DOOR_Y_BACK = 0.600                           # leaf back face (frame front at 0.598)
DOOR_Y_FRONT = 0.623                          # leaf front face (cell plane at 0.625)
DOOR_AXIS_X = 0.5 - DOOR_HINGE_INSET          # 0.474
DOOR_AXIS_Y = (DOOR_Y_BACK + DOOR_Y_FRONT) / 2   # 0.6115
DOOR_HALF_T = (DOOR_Y_FRONT - DOOR_Y_BACK) / 2   # 0.0115
DOOR_KNUCKLE_R = 0.011                        # hinge barrel radius (flush with both leaf faces)
DOOR_U0 = 0.013                               # leaf panel starts this far from the axis (clear of the barrel)
DOOR_MEET_GAP = 0.0015                        # each leaf stops this far short of the rack centre line
DOOR_W = DOOR_AXIS_X - DOOR_MEET_GAP          # 0.4725: axis to free edge (= half the opening between the axes)
DOOR_Z_GAP = 0.004                            # leaves stop 4 mm inside the slot band (plinth top, tray / roof)
DOOR_OPEN_DEG = 85.0                          # the cap (spec): neighbours clear by the knuckle margin
DOOR_SECONDS = 1.0                            # DoorServerDefinition.OpeningDuration (linear, no easing)

# ---------------------------------------------------------------------------------------------------- tray fans
FAN_X = (-0.2, 0.2)                           # two exhaust fans in the tray's rear lane (full racks)
FAN_Y = -0.305
FAN_R = 0.095                                 # rotor tip radius; the opening is FAN_R + 6 mm

# ---------------------------------------------------------------------------------------------------- rack top tray
# (moved here from dc/rack.py: the cable trays couple to them)
RACK_TRAY_IX = 0.44                           # full-rack top trough interior half width (clear of the corner caps)
RACK_TRAY_IY = 0.46                           # ... and half depth: the rim's inner edge
MANAGER_CH_X = (0.297, 0.42)                  # |x| of the vertical cable-manager channel in each side column
MANAGER_SPINE_Y = (0.393, 0.405)              # |y| of the channel's back wall (front channel; mirrored at the rear)

# ---------------------------------------------------------------------------------------------------- tray interface
# Cable trays: where an overhead tray run meets a rack. Rack-local, centred frame, +Y = front. The tray's
# waterfalls leave over the tray's front wall and drop into the front cable managers through the top-entry brush
# plates (dc/rack.py _entry_plate / _brush_lips); the tray plan (dc/tray_plan.py) builds the Drop from these only.
TRAY_RACK_Y = 0.125                           # tray centreline: 1/2 cell in front of the rack centre (a grid line)
TRAY_HANG = 0.5                               # tray's lowest cell plane above the full-rack top plane
FLOOR_Z = 0.045                               # tray floor top above the grid plane behind the floor (lane contract)
WF_X = (MANAGER_CH_X[0] + MANAGER_CH_X[1]) / 2           # 0.3585: waterfall |x| = the manager channel centre
WF_Y = (MANAGER_SPINE_Y[1] + RACK_TRAY_IY) / 2           # 0.4325: the manager entry's centre (spine .. rim)
R_WF = 0.0225                                 # waterfall bundle radius (7 cables of r 7.5 mm)
ROD_S = 0.232                                 # trapeze rods at the tray centreline +- ROD_S (across)
TOP_ENTRY = (MANAGER_CH_X, (MANAGER_SPINE_Y[1], RACK_TRAY_IY))   # |x| and y of the full rack's brush-plate opening
ENTRY_FLANGE = 0.008                          # the brush plate's frame stands this far round the opening
ENTRY_DROP = 0.001                            # the plate's top sits this far under the rack's top plane
ENTRY_EDGE = 0.004                            # the Yellow edge: the frame's inner band round the opening
# the half rack's roof-rail entries (front; mirrored at the rear for the power manager): the roof-rail holes,
# their inner edge moved 4 mm out so the same plate (opening + flange) keeps 4.5 mm of rail toward the slot roof
HALF_TOP_ENTRY = ((MANAGER_CH_X[0] + 0.016, MANAGER_CH_X[1] - 0.004), (MANAGER_SPINE_Y[1], 0.466))


def rack_frame(ny):
    """The rack's vertical layout from its height in cells (10 = full rack with a top tray, 5 = half rack):
    (H, ZT, tray, nslots); ZT = the top of the slot band (local z, 0 = floor). Used by dc/rack.py and dc/doors.py."""
    tray = ny == 10
    nslots = ny - 2 if tray else ny - 1
    return 0.25 * ny, 0.25 + SLOT_H * nslots, tray, nslots


# ---------------------------------------------------------------------------------------------------- room interface
# Room pieces: where the raised floor, the aisle containment, the PDU strips and the rack labels meet the
# racks. Rack-local, centred frame, +Y = front; |y| values are mirrored at the back. dc/rack.py builds these, the
# build measures them back (build_report "geometry": contain_rails, pdu_receptacles, pdu_envelope_clear,
# up_mount_rects / down_mount_rects) and Tests/test_room_interface.py checks the couplings on the measurements.
RF_H = 0.25                                   # raised-floor height (one cell; the rack plinth stands on its top plane)
RF_TILE = 0.5                                 # floor tile pitch (two cells)
RF_DECK_T = 0.032                             # tile deck thickness (top plate + perforated sheet)
AISLE_WIDTHS = (1.0, 1.5, 2.0)                # containment door / roof widths (each half lands on a grid plane)
# the containment rail: a Colorable box rail across the full racks' front and back tray band; the roof panels' edges
# bear on it and their clamps grip its pads (real racks take aisle-containment brackets on top). |y| band: from the
# door leaves' back face plane to 1 mm inside the cell plane; z band above ZT (the slot band's top)
CONTAIN_RAIL_Y = (0.600, 0.624)
CONTAIN_RAIL_DZ = (0.012, 0.238)
ROOF_CLEAR = 0.004                            # anything that moves into the aisle stays this far under a roof panel
# the freed rear PDU columns (the zero-U PDU strips' cells, Feed A = +x, Feed B mirrored at -x), the slot band
PDU_COL_X = (0.25, 0.5)
PDU_COL_Y = (-0.625, -0.375)
# the largest box in the column clear of the frame (measured on the built LOD0):
# x from 2 mm outside the 19" rail's outer face (0.29) to 2 mm inside the corner post's inner face (0.4225);
# y from 2 mm behind the PDU bulkhead's face (0.3745) to 2 mm inside the frame's rear plane (0.598 = YK)
PDU_ENVELOPE = ((0.292, 0.420), (-0.596, -0.377))
PDU_RECEPTACLE = ((PDU_ENVELOPE[0][0] + PDU_ENVELOPE[0][1]) / 2, (PDU_ENVELOPE[1][0] + PDU_ENVELOPE[1][1]) / 2)
# (0.356, -0.4865): the PDU inlet's twist-lock socket, flush in the plinth top (z = 0.25 local)
LABEL_X = (-0.25, 0.25)                       # the rack-top label pad (front; mirrored for the back): two cells wide,
LABEL_Y = (0.375, 0.625)                      # the front cell deep
TRAY_END_INSET = 0.001                        # strut end plates and rod ends stay 1 mm inside the box
# The cable trays' rod-coupler plate. A deliberate duplicate of dc/tray_plan.ROD_PLATE; tray_plan should import
# ROD_PLATE / TRAY_END_INSET from here. Pinned equal by Tests/test_room_interface.py::test_rod_plate_single_source.
ROD_PLATE = 2 * (CELL - ROD_S - TRAY_END_INSET)   # 0.034

# ---------------------------------------------------------------------------------------------------- PDU cords
# Where power cords start and end, single-sourced for future neighbor-aware "live cabling": a pre-modelled cord
# from a strip outlet to a server inlet needs both ends from here. Rack-local, centred x / y (the PDU strip's Feed A
# column, +x; Feed B mirrored at -x), z slot-relative (0 = the slot's floor; slot k's floor is local
# z 0.25 + SLOT_H * (k - 1)).
#   * the zero-U strip (dc/pdu.py): per slot a pair of locking outlets side by side, on the strip's face toward the
#     rear opening, at one slot-relative height; PDU_OUTLET_FACE_Y is the outlet's socket face (where a plug seats);
#   * the server (dc/server.py _rear): two hot-swap PSUs on the rear panel's +x half, each with its power inlet;
#     SERVER_INLET_FACE_Y is the inlet's socket face (server-local y; the server's cell is the slot, so rack-local too).
PDU_STRIP_CX = 0.373                          # |x| of the strip body's centre line (body |x| 0.328 .. 0.418)
PDU_OUTLET_X = (0.351, 0.395)                 # |x| of the pair's centres: inner (toward the servers), outer
PDU_OUTLET_FACE_Y = -0.506                    # the outlet sockets' face (the strip's body face at -0.500, 6 mm proud)
PDU_OUTLET_Z = 0.100                          # slot-relative z of the pair's centre (low in the slot: the half rack's
#                                               PDU band stops at local z 1.13, 3 cm into its top slot)
PDU_OUTLET_SIZE = (0.036, 0.032)              # an outlet housing (across x, along z)
SERVER_PSU_X = ((0.098, 0.152), (0.158, 0.212))   # the server's two PSU bays (x, rear panel; A then B)
SERVER_INLET_B = (0.012, 0.040)               # the inlet shell's z above the PSU module's foot (slot z 0.016)
SERVER_INLET_FACE_Y = -0.363                  # the inlet's face (server rear plate -0.372, module 16 mm in, shell 7 mm)


def pdu_outlets(nslots, feed="A"):
    """[(slot 1..n, outlet 0 inner / 1 outer, (x, y, z))]: every strip outlet's socket centre, rack-local (z: 0 = the
    floor under the rack, i.e. its plinth bottom). Feed B mirrors x."""
    sx = 1 if feed == "A" else -1
    return [(k + 1, i, (sx * x, PDU_OUTLET_FACE_Y, round(0.25 + SLOT_H * k + PDU_OUTLET_Z, 6)))
            for k in range(nslots) for i, x in enumerate(PDU_OUTLET_X)]


def server_inlets():
    """[(PSU 0 / 1, (x, y, z))]: a 6U server's two power inlets, server-local x / y, z slot-relative (inlet centre)."""
    z = 0.016 + (SERVER_INLET_B[0] + SERVER_INLET_B[1]) / 2
    return [(i, (round((a + b) / 2, 6), SERVER_INLET_FACE_Y, round(z, 6))) for i, (a, b) in enumerate(SERVER_PSU_X)]
