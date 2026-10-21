// Data Center probe (adapted from an earlier prototype's mount-point probe).
// Run in game via se2-game execute_code (usings: System.Linq, System.Reflection, System.Collections.Generic)
// or: tools/scripts/se2game.py exec -f mods/DataCenter/Source/Model/review/probe_mountpoints.csx
// Place one of each Data Center block first. Per distinct placed block definition it prints the generated placement
// data (bounding box, occupied cells, mount groups per face) to compare with check_placement.py / build_report.json,
// and the Task 10 data: display size and assigned BlockSize (menu grouping), mass, and the in-game cost
// (Items = recipe x the game's mass scale; dc/recipes.py predicts scale 1 and the amounts in NOTES.md).
var needles = new[] { "DC_Rack", "DC_Srv_", "DC_Tray" };
var s = Singleton<VRageCore>.Instance.Engine.Get<GameAppComponent>().ClientSession;
var seen = new System.Collections.Generic.HashSet<string>();
object P(object o, string n) { try { return o?.GetType().GetProperty(n, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(o); } catch { return null; } }
foreach (var e in s.Entities) {
  CubeBlockComponent cb = null; try { cb = e.Get<CubeBlockComponent>(); } catch {}
  if (cb == null) continue;
  var d = cb.Definition; var ds = d.ToString();
  if (!needles.Any(n => ds.Contains(n)) || !seen.Add(ds)) continue;
  Console.WriteLine("== " + ds);
  Console.WriteLine("  BoundingBox: " + d.BoundingBox);
  var occ = P(d, "OccupiedGridCellsGroups") as System.Collections.IEnumerable;
  if (occ != null) Console.WriteLine("  Occupied: " + string.Join(" | ", occ.Cast<object>()));
  Console.WriteLine($"  DisplaySize {P(d, "DisplaySize")}  RelativeBlockSize {P(P(d, "RelativeBlockSize"), "RelativeBlockSize")}  BlockKind {P(d, "BlockKind")}");
  Console.WriteLine($"  Mass {P(d, "Mass")}  MaxHealth {P(d, "MaxHealth")}  TotalItemAmount {P(d, "TotalItemAmount")}  OptionalItemAmount {P(d, "OptionalItemAmount")}");
  var items = P(d, "Items") as System.Collections.IEnumerable;
  if (items != null) Console.WriteLine("  Items: " + string.Join(", ", items.Cast<object>().Select(i => $"{P(i, "Amount")} x {P(i, "Item")}")));
  var dict = P(d, "MountPointsGroupsPerDirection") as System.Collections.IEnumerable;
  if (dict == null) continue;
  foreach (var kv in dict) {
    var key = kv.GetType().GetProperty("Key").GetValue(kv);
    var list = (kv.GetType().GetProperty("Value").GetValue(kv) as System.Collections.IEnumerable).Cast<object>().ToList();
    Console.WriteLine($"  {key}: {list.Count} mount group(s)");
  }
}
