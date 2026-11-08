"""Rebuild an inspectable inventory from the running contracts, without contacting engines."""
import ast
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))     # vt/ lives in server/ since the client/server split


def main():
    from vt.modules.defs import load
    from vt.modules.registry import list_modules, lint_registry
    from vt.planner.catalogue import component_catalogue
    from vt.server.app import app
    load()
    modules = [{"id":m.id,"name":m.plain_name,"purpose":m.summary,"toolboxes":list(m.toolboxes),
                "source":str(Path(inspect.getfile(m.run)).relative_to(ROOT)).replace("\\","/"),
                "requires":list(m.requires),"produces":list(m.produces),"effects":m.effects,
                "studio_form": "studio" in m.toolboxes and m.effects != "external_post"} for m in list_modules()]
    routes = [{"path":r.path,"methods":sorted(r.methods)} for r in app.routes if getattr(r,"methods",None) and r.path.startswith("/api/")]
    components=[{"type":c["type"],"name":c["name"],"category":c["category"]} for c in component_catalogue()]
    pages=[p.stem for p in sorted((ROOT/"client/studio/src/pages").glob("*.tsx"))]
    plans=[str(p.relative_to(ROOT)).replace("\\","/") for p in sorted((ROOT/"docs/plans").glob("*.MD"))]
    inventory={"modules":modules,"components":components,"routes":routes,"pages":pages,"plans":plans,"registry_errors":lint_registry()}
    target=ROOT/"docs/evidence/capability-inventory.json"
    target.write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"modules":len(modules),"autonomous":sum("autonomous" in m["toolboxes"] for m in modules),
                      "studio_forms":sum(m["studio_form"] for m in modules),"components":len(components),"api_routes":len(routes),
                      "pages":len(pages),"registry_errors":inventory["registry_errors"]}))


if __name__=="__main__":
    main()
