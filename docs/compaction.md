# Compaction and Maintenance

RecallLayer now has two layers of maintenance logic:

## 1. Compaction planner / executor

The existing compaction planner chooses candidate segments within a shard based on:

- delete ratio
- generation age
- row count

The executor then materializes a replacement segment, retires old segments, and updates the shard manifest.

## 2. Adaptive maintenance policy

The newer adaptive maintenance layer ranks shards before compaction. It considers:

- active segment count (fragmentation pressure)
- delete ratio
- total sealed-row pressure
- mutable-buffer pressure

This gives the engine a simple background-maintenance strategy instead of only a static yes/no threshold.

## Why this matters

A real storage engine should not only know *how* to compact; it should have a reasonable answer for *which shard to compact next* when multiple shards are eligible.

## Main surfaces

- `recalllayer.engine.compaction_planner.CompactionPlanner`
- `recalllayer.engine.compaction_executor.CompactionExecutor`
- `recalllayer.engine.compaction_policy.CompactionPolicy`
- `recalllayer.engine.maintenance.AdaptiveMaintenancePlanner`
- `recalllayer.engine.maintenance.AdaptiveMaintenancePolicy`
