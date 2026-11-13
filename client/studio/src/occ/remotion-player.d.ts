// Video Tool: the ported OpenChatCut timeline names Remotion's PlayerRef type only. Video Tool has its own preview player; it is wrapped to
// this shape (src/occ/bridge/playerAdapter.ts), so the timeline drives it the same way. Only the members the timeline uses are declared.
declare module '@remotion/player' {
  export interface CallbackEvents {
    frameupdate: { frame: number };
    play: undefined;
    pause: undefined;
    ended: undefined;
    seeked: { frame: number };
  }
  export type CallbackListener<T extends keyof CallbackEvents> = (data: { detail: CallbackEvents[T] }) => void;
  export interface PlayerRef {
    seekTo(frame: number): void;
    getCurrentFrame(): number;
    play(): void;
    pause(): void;
    toggle(): void;
    isPlaying(): boolean;
    isFullscreen(): boolean;
    requestFullscreen(): void;
    exitFullscreen(): void;
    getContainerNode(): HTMLDivElement | null;
    addEventListener<T extends keyof CallbackEvents>(type: T, listener: CallbackListener<T>): void;
    removeEventListener<T extends keyof CallbackEvents>(type: T, listener: CallbackListener<T>): void;
  }
}
