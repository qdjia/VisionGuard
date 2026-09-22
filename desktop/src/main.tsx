import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { createRuntimeManagedBackend } from "./api/client";
import { tauriImageSource } from "./platform/imageSource";
import { tauriRuntimeController } from "./runtime/client";
import "./styles/tokens.css";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App
      backend={createRuntimeManagedBackend(tauriRuntimeController)}
      imageSource={tauriImageSource}
      runtime={tauriRuntimeController}
    />
  </StrictMode>,
);
