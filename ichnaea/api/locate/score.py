import math


def area_score(obj, now):
    # Return a score for an area.
    return score(obj, now, area_score_created, area_score_samples)


def station_score(obj, now):
    # Return a score for a station.
    return score(obj, now, station_score_created, station_score_samples)


def score(obj, now, score_created, score_samples):
    # Returns a score as a floating point number.
    # The score represents the quality or trustworthiness of this record.

    # age_weight is a number between:
    # 1.0 (data from last month) to
    # 0.277 (data from a year ago)
    # 0.2 (data from two years ago)
    month_old = max((now - obj.modified).days, 0) // 30
    age_weight = 1 / math.sqrt(month_old + 1)

    # collection_weight is a number between:
    # 0.1 (data was only seen on a single day)
    # 0.2 (data was seen on two different days)
    # 1.0 (data was first and last seen at least 10 days apart)
    last_seen = obj.modified.date()
    if obj.last_seen is not None:
        last_seen = max(last_seen, obj.last_seen)

    collected_over = max(
        (last_seen - score_created(obj)).days, 1)
    collection_weight = min(collected_over / 10.0, 1.0)

    return age_weight * collection_weight * score_samples(obj)


def area_score_created(obj):
    # Areas don't keep track of blocklisting / movements.
    return obj.created.date()


def station_score_created(obj):
    # The creation date stays intact after a station moved to a new
    # position. For scoring purposes we only want to consider how
    # long the station has been at its current position.
    created = obj.created.date()
    if not obj.block_last:
        return created
    return max(created, obj.block_last)


def area_score_samples(obj):
    # treat areas for which we get the exact same
    # cells multiple times as if we only got 1 cell
    samples = obj.num_cells
    if samples > 1 and not obj.radius:
        samples = 1

    # sample_weight is a number between:
    # 1.0 for 1 sample
    # 1.41 for 2 samples
    # 10 for 100 samples
    # we use a sqrt scale instead of log2 here, as this represents
    # the number of cells in an area and not the sum of samples
    # from all cells in the area
    return min(math.sqrt(max(samples, 1)), 10.0)


def station_score_samples(obj):
    # treat networks for which we get the exact same
    # observations multiple times as if we only got 1 sample
    samples = obj.samples
    if samples > 1 and not obj.radius:
        samples = 1

    # sample_weight is a number between:
    # 0.5 for 1 sample
    # 1.0 for 2 samples
    # 3.32 for 10 samples
    # 6.64 for 100 samples
    # 10.0 for 1024 samples or more
    return min(max(math.log(max(samples, 1), 2), 0.5), 10.0)
