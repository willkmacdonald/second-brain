import { useEffect, useState } from "react";
import { Linking, Pressable, StyleSheet, Text, View } from "react-native";
import {
  fetchSpineStatus,
  SegmentStatus,
  SpineSegment,
  SPINE_WEB_URL,
} from "../lib/spine";

const COLOR: Record<SegmentStatus, string> = {
  green: "#3a7d3a",
  yellow: "#c89010",
  red: "#b33b3b",
  stale: "#555",
};

interface Props {
  segmentId: string;
}

export function SpineStatusTile({ segmentId }: Props) {
  const [segment, setSegment] = useState<SpineSegment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchSpineStatus();
        if (cancelled) return;
        const found = data.segments.find((s) => s.id === segmentId) ?? null;
        setSegment(found);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
      }
    }
    load();
    const id = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [segmentId]);

  function handlePress() {
    if (!SPINE_WEB_URL) return;
    Linking.openURL(`${SPINE_WEB_URL}/segment/${segmentId}`);
  }

  if (error) {
    return (
      <View style={[styles.tile, { borderColor: COLOR.stale }]}>
        <Text style={styles.title}>Spine unreachable</Text>
        <Text style={styles.headline}>{error}</Text>
      </View>
    );
  }

  if (!segment) {
    return (
      <View style={[styles.tile, { borderColor: COLOR.stale }]}>
        <Text style={styles.title}>Loading…</Text>
      </View>
    );
  }

  return (
    <Pressable onPress={handlePress} style={[styles.tile, { borderColor: COLOR[segment.status] }]}>
      <View style={styles.row}>
        <Text style={styles.title}>{segment.name}</Text>
        <Text style={[styles.status, { color: COLOR[segment.status] }]}>
          {segment.status.toUpperCase()}
        </Text>
      </View>
      <Text style={styles.headline}>{segment.headline}</Text>
      <Text style={styles.freshness}>{segment.freshness_seconds}s ago</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  tile: {
    padding: 16,
    backgroundColor: "#1a2028",
    borderWidth: 2,
    borderRadius: 8,
    marginBottom: 12,
  },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  title: { fontSize: 16, fontWeight: "600", color: "#e6e6e6" },
  status: { fontSize: 12 },
  headline: { color: "#bbb", marginTop: 8, fontSize: 14 },
  freshness: { color: "#666", marginTop: 8, fontSize: 11 },
});
