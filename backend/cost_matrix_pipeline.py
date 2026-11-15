"""GIS cost pipeline (Friend 1): DEM + radiation -> A*-ready cost matrix."""
import numpy as np

def generate_cost_matrix(elevation_grid, radiation_grid, resolution_meters=10.0, max_safe_slope=15.0,
                         w1=0.6, w2=0.4, origin_lat=-5.413, origin_lon=137.442, min_step_cost=0.05):
    """Cost = w1*slope_deg + w2*radiation_norm + min_step_cost. Slope > max_safe_slope, or missing (NaN)
    elevation, is impassable (np.inf): unknown ground is never treated as safe.
    origin_lat/lon: coordinates of cell (0,0), the north-west corner (pass the site you are actually mapping)."""
    elev = np.asarray(elevation_grid, dtype=float); rad = np.asarray(radiation_grid, dtype=float)
    if elev.shape != rad.shape:
        raise ValueError(f"Shape mismatch: elevation {elev.shape} vs radiation {rad.shape}")
    if resolution_meters <= 0 or w1 < 0 or w2 < 0:
        raise ValueError("resolution_meters must be > 0 and weights >= 0")
    d_row, d_col = np.gradient(elev, resolution_meters)               # axis 0 = rows, axis 1 = columns
    slope_deg = np.degrees(np.arctan(np.hypot(d_row, d_col)))
    slope_cost = np.where(np.isnan(elev) | np.isnan(slope_deg) | (slope_deg > max_safe_slope), np.inf, slope_deg)
    rad_clean = np.nan_to_num(rad, nan=np.nanmean(rad) if not np.all(np.isnan(rad)) else 0.0)
    span = rad_clean.max() - rad_clean.min()
    rad_cost = np.zeros_like(rad_clean) if span == 0 else (rad_clean - rad_clean.min()) / span
    total = w1 * slope_cost + w2 * rad_cost + min_step_cost
    total[np.isinf(slope_cost)] = np.inf
    return {"total_cost_matrix": total, "slope_degrees": slope_deg, "radiation_cost": rad_cost,
            "spatial_bounds": {"origin_lat": origin_lat, "origin_lon": origin_lon, "resolution_meters": resolution_meters},
            "dimensions": total.shape}

def make_mock_dem(size=200, seed=42, amplitude_m=40.0):
    """Smooth, low-frequency mock terrain (FFT-filtered noise) so slopes look like terrain, not static."""
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.standard_normal((size, size)))
    ky, kx = np.meshgrid(np.fft.fftfreq(size), np.fft.fftfreq(size), indexing="ij")
    f *= np.exp(-(kx**2 + ky**2) / (2 * 0.02**2))
    dem = np.real(np.fft.ifft2(f)); return amplitude_m * dem / np.abs(dem).max()

if __name__ == "__main__":
    import sys
    dem = make_mock_dem(); rad = np.random.default_rng(1).random(dem.shape)
    res = generate_cost_matrix(dem, rad); m = res["total_cost_matrix"]
    print("shape", m.shape, "| impassable %.1f%%" % (100*np.isinf(m).mean()), "| max slope %.1f deg" % res["slope_degrees"].max())
    if "--plot" in sys.argv:
        import matplotlib.pyplot as plt
        plt.imshow(np.where(np.isinf(m), np.nan, m), cmap="plasma", origin="upper"); plt.colorbar(label="cost (blank = impassable)"); plt.show()
