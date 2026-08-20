import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

export const dynamic = "force-dynamic";

export async function GET() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) {
    return NextResponse.json({
      window_minutes: 30,
      active_total: 0,
      locations: [],
      mode: "no-activity",
      reason: "Supabase activity source is not configured",
    });
  }

  const supabase = createClient(url, anonKey, { auth: { persistSession: false } });
  const cutoff = new Date(Date.now() - 30 * 60 * 1000).toISOString();
  const { data, error } = await supabase
    .from("globe_activity_rollups")
    .select("label,lat,lon,active_count,bucket_start")
    .gte("bucket_start", cutoff)
    .order("bucket_start", { ascending: false })
    .limit(250);

  if (error) {
    return NextResponse.json({
      window_minutes: 30,
      active_total: 0,
      locations: [],
      mode: "no-activity",
      reason: "Observed activity rollups are unavailable",
    });
  }

  const merged = new Map<string, { label: string; lat: number; lon: number; count: number }>();
  for (const row of data ?? []) {
    const key = `${row.label}:${row.lat}:${row.lon}`;
    const existing = merged.get(key);
    if (existing) existing.count += Number(row.active_count || 0);
    else merged.set(key, { label: row.label, lat: Number(row.lat), lon: Number(row.lon), count: Number(row.active_count || 0) });
  }
  const locations = Array.from(merged.values()).sort((a, b) => b.count - a.count).slice(0, 50);
  const activeTotal = locations.reduce((sum, item) => sum + item.count, 0);

  return NextResponse.json({
    window_minutes: 30,
    active_total: activeTotal,
    locations,
    mode: activeTotal > 0 ? "observed-aggregate" : "no-activity",
  });
}
