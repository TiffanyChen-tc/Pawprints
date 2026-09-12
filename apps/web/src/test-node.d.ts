declare module "node:fs" {
  export function readFileSync(path: string, encoding: BufferEncoding): string;
}

declare module "node:path" {
  export function join(...paths: string[]): string;
}

declare type BufferEncoding = "utf-8" | "utf8";

declare const process: {
  cwd(): string;
};
