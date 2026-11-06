import { post } from "./api";
import { toast } from "./store";

/** Show a video's exports folder. It opens on this computer only when the server is this computer; otherwise the files are on the server and the person is told where. */
export function openFolder(id: string) {
  post<{ path: string; opened: boolean }>(`/api/projects/${id}/open-folder`)
    .then((r) => { if (!r.opened) toast(`The finished files are on the server computer, in ${r.path}. Use Download to get them on this one.`, "ok", 9000); })
    .catch((e) => toast(e.message, "err"));
}
