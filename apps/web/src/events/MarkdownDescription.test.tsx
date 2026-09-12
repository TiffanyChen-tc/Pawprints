import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MarkdownDescription from "./MarkdownDescription";

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
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.queryByAltText("alt")).toBeNull();
    expect(screen.queryByText("raw")).toBeNull();
    expect(document.querySelector("table")).toBeNull();
    expect(document.querySelector("code")).toBeNull();
    expect(document.querySelector("input[type='checkbox']")).toBeNull();
    expect(screen.getByText("bold").tagName.toLowerCase()).toBe("strong");
    expect(screen.getByText("item").tagName.toLowerCase()).toBe("li");
  });
});
