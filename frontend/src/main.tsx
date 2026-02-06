import React from "react";
import ReactDOM from "react-dom/client";
import { UploadPage } from "./upload-page";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <UploadPage />
  </React.StrictMode>
);

