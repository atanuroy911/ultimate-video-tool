// Video Tool: our preview player in the shape of Remotion's PlayerRef, which the ported OpenChatCut timeline drives (seek, play, pause, and
// "frameupdate" / "play" / "pause" events). The clock is our timeStore (the audio clock writes it every frame); play state comes from
// Preview's onPlaying, passed in through `setPlaying`.
import type { CallbackEvents, CallbackListener, PlayerRef } from '@remotion/player';
import type { RefObject } from 'react';
import type { PlayerHandle } from '../../review/Preview';
import { timeStore } from '../../review/timeStore';

export interface PlayerAdapter extends PlayerRef {
  /** Preview's onPlaying: tells the timeline that playback started or stopped */
  setPlaying(playing: boolean): void;
  /** the frame rate the timeline counts in */
  fps: number;
}

export function makePlayerAdapter(handle: RefObject<PlayerHandle>, fps: number): PlayerAdapter {
  const listeners: { [K in keyof CallbackEvents]: Set<CallbackListener<K>> } = {
    frameupdate: new Set(), play: new Set(), pause: new Set(), ended: new Set(), seeked: new Set(),
  };
  const emit = <K extends keyof CallbackEvents>(type: K, detail: CallbackEvents[K]) => {
    for (const l of listeners[type]) (l as CallbackListener<K>)({ detail });
  };
  let playing = false;
  let unsubscribe: (() => void) | null = null;
  const frameOf = (t: number) => Math.max(0, Math.round(t * fps));
  const watchClock = () => {
    if (!unsubscribe && listeners.frameupdate.size) unsubscribe = timeStore.subscribe((t) => emit('frameupdate', { frame: frameOf(t) }));
    if (unsubscribe && !listeners.frameupdate.size) { unsubscribe(); unsubscribe = null; }
  };
  const adapter: PlayerAdapter = {
    fps,
    seekTo(frame) {
      handle.current?.seek(Math.max(0, frame) / fps);
      emit('seeked', { frame: Math.max(0, frame) });
    },
    getCurrentFrame: () => frameOf(timeStore.t),
    play() { if (!handle.current?.isPlaying()) handle.current?.toggle(); },
    pause() { if (handle.current?.isPlaying()) handle.current?.toggle(); },
    toggle() { handle.current?.toggle(); },
    isPlaying: () => handle.current?.isPlaying() ?? playing,
    isFullscreen: () => !!document.fullscreenElement,
    requestFullscreen() { /* the Studio's Focus button owns full screen */ },
    exitFullscreen() { if (document.fullscreenElement) void document.exitFullscreen(); },
    getContainerNode: () => null,
    addEventListener(type, listener) {
      (listeners[type] as Set<typeof listener>).add(listener);
      if (type === 'frameupdate') watchClock();
    },
    removeEventListener(type, listener) {
      (listeners[type] as Set<typeof listener>).delete(listener);
      if (type === 'frameupdate') watchClock();
    },
    setPlaying(next) {
      if (next === playing) return;
      playing = next;
      emit(next ? 'play' : 'pause', undefined);
    },
  };
  return adapter;
}
