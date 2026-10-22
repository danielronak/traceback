import { render } from "preact";
import { App } from "./app";
import { registerServiceWorker } from "./offline";
import "./styles.css";

render(<App />, document.getElementById("app")!);
registerServiceWorker();
