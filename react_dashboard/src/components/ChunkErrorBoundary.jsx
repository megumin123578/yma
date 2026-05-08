import { Component } from "react";

const RELOAD_FLAG_KEY = "chunkReloadAt";
const RELOAD_COOLDOWN_MS = 30 * 1000;

const isChunkLoadError = (error) => {
    if (!error) return false;
    const name = String(error.name || "");
    const message = String(error.message || "");
    return (
        name === "ChunkLoadError" ||
        /Loading chunk [\w-]+ failed/i.test(message) ||
        /Failed to fetch dynamically imported module/i.test(message) ||
        /Importing a module script failed/i.test(message)
    );
};

class ChunkErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { error: null };
    }

    static getDerivedStateFromError(error) {
        return { error };
    }

    componentDidCatch(error) {
        if (!isChunkLoadError(error)) return;
        // Avoid reload loops: only auto-reload once per 30s window.
        try {
            const last = Number(sessionStorage.getItem(RELOAD_FLAG_KEY) || 0);
            if (Date.now() - last < RELOAD_COOLDOWN_MS) return;
            sessionStorage.setItem(RELOAD_FLAG_KEY, String(Date.now()));
        } catch {
            // sessionStorage may be unavailable — fall through to reload anyway
        }
        window.location.reload();
    }

    render() {
        if (this.state.error && !isChunkLoadError(this.state.error)) {
            // Non-chunk errors: re-throw so other layers can handle (or log via window.onerror).
            throw this.state.error;
        }
        return this.props.children;
    }
}

export default ChunkErrorBoundary;
