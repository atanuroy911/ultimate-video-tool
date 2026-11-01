/** The playhead time, outside React: the audio clock updates it every frame and only the few things that must follow it listen, so the rest of the editor does not re-render 60 times a second. */
type Fn = (t: number) => void;
const subs = new Set<Fn>();
export const timeStore = {
  t: 0,
  playing: false,
  set(t: number) {
    if (t === this.t) return;
    this.t = t;
    subs.forEach((f) => f(t));
  },
  subscribe(f: Fn) {
    subs.add(f);
    return () => {
      subs.delete(f);
    };
  },
};
