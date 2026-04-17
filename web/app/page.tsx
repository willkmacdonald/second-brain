import { spine } from "@/lib/spine";
import { StatusBoard } from "@/components/StatusBoard";

export const dynamic = "force-dynamic"; // never statically render
export const revalidate = 0;

export default async function Page() {
  const board = await spine.status();
  return (
    <main style={{ padding: 24 }}>
      <h1 style={{ marginTop: 0 }}>Second Brain — Spine</h1>
      <StatusBoard data={board} />
    </main>
  );
}
