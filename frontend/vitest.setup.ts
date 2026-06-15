// Registers jest-dom matchers (toBeInTheDocument, toHaveTextContent, ...) on Vitest's expect.
import "@testing-library/jest-dom/vitest";
// RTL auto-cleanup only fires when `afterEach` is in global scope (globals:true).
// Since this project uses globals:false, register cleanup explicitly.
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
afterEach(() => cleanup());
