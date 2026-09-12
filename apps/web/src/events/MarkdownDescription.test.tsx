import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import "../styles.css";
import MarkdownDescription from "./MarkdownDescription";

const stylesSource = readFileSync(join(process.cwd(), "src", "styles.css"), "utf-8");

describe("MarkdownDescription", () => {
  it("renders only the approved inline/list subset and suppresses raw html", () => {
    render(
      <MarkdownDescription
        source={
          "**bold**\n\n- item\n\n# Heading\n[link](https://example.com)\n![alt](https://example.com/a.png)\n<div>raw</div>\n\n| A | B |\n| - | - |\n| 1 | 2 |\n\n```js\ncode\n```\n- [ ] task"
        }
      />,
    );

    expect(screen.queryByRole("heading")).toBeNull();
    expect(screen.getByRole("link", { name: "link" })).toHaveAttribute("href", "https://example.com");
    expect(screen.queryByAltText("alt")).toBeNull();
    expect(screen.queryByText("raw")).toBeNull();
    expect(document.querySelector("table")).toBeNull();
    expect(document.querySelector("code")).toBeNull();
    expect(document.querySelector("input[type='checkbox']")).toBeNull();
    expect(screen.getByText("bold").tagName.toLowerCase()).toBe("strong");
    expect(screen.getByText("item").tagName.toLowerCase()).toBe("li");
  });

  it("renders safe Markdown links and suppresses unsafe protocols", () => {
    render(<MarkdownDescription source={"[safe](https://example.com) [unsafe](javascript:alert(1))"} />);

    expect(screen.getByRole("link", { name: "safe" })).toHaveAttribute("href", "https://example.com");
    expect(screen.queryByRole("link", { name: "unsafe" })).toBeNull();
    expect(screen.getByText("unsafe")).toBeInTheDocument();
  });

  it("visibly renders emphasized Diary text as italic", () => {
    render(<MarkdownDescription source={"*visible italic*"} />);

    expect(getComputedStyle(screen.getByText("visible italic")).fontStyle).toBe("italic");
  });

  it("allows browsers to synthesize an italic face when the active font has no italic variant", () => {
    expect(stylesSource).toContain("font-synthesis: style;");
  });
});
