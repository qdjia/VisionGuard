import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { createBackend } from "./api/client";
import { tauriImageSource } from "./platform/imageSource";
import "./styles/tokens.css";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(<StrictMode><App backend={createBackend()} imageSource={tauriImageSource} /></StrictMode>);
