import { Component, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

/** If something in a page breaks while it is drawn, the person sees what happened in plain words and a way out, never a blank screen. */
class Catch extends Component<{ children: ReactNode }, { broke: boolean }> {
  state = { broke: false };
  static getDerivedStateFromError() { return { broke: true }; }
  componentDidCatch(error: unknown) { console.error("page error", error); }
  render() {
    if (!this.state.broke) return this.props.children;
    return (
      <div className="page-inner" role="alert" style={{ maxWidth: 560, margin: "12vh auto", padding: "0 16px" }}>
        <h2>Something went wrong on this page</h2>
        <p className="muted">Your videos are safe. Reload the page to try again, or go back to your videos. If it keeps happening, Settings → Is everything working? shows what the server sees.</p>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn primary" onClick={() => window.location.reload()}>Reload this page</button>
          <a className="btn" href="/">Your videos</a>
        </div>
      </div>
    );
  }
}

/** One boundary for each address, so going to another page clears the message. */
export default function ErrorBoundary({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return <Catch key={pathname}>{children}</Catch>;
}
