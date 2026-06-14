import { describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ToastProvider, useToast } from "./Toast";

function Trigger() {
  const { showToast } = useToast();
  return <button onClick={() => showToast({ message: "Run #12 failed", href: "/dashboard/history" })}>fire</button>;
}

describe("Toast", () => {
  it("shows a toast message when showToast is called", async () => {
    render(<ToastProvider><Trigger /></ToastProvider>);
    expect(screen.queryByText("Run #12 failed")).not.toBeInTheDocument();
    await act(async () => { screen.getByText("fire").click(); });
    expect(screen.getByText("Run #12 failed")).toBeInTheDocument();
  });
});
