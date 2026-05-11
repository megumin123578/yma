import { useEffect, useState } from "react";

let cachedGeoFeatures = null;
let pendingPromise = null;

const loadGeoFeatures = () => {
  if (cachedGeoFeatures) return Promise.resolve(cachedGeoFeatures);
  if (pendingPromise) return pendingPromise;
  pendingPromise = import("../data/mockGeoFeatures").then((mod) => {
    cachedGeoFeatures = mod.geoFeatures;
    return cachedGeoFeatures;
  });
  return pendingPromise;
};

export const useGeoFeatures = () => {
  const [data, setData] = useState(cachedGeoFeatures);

  useEffect(() => {
    if (cachedGeoFeatures) {
      if (data !== cachedGeoFeatures) setData(cachedGeoFeatures);
      return;
    }
    let mounted = true;
    loadGeoFeatures().then((res) => {
      if (mounted) setData(res);
    });
    return () => {
      mounted = false;
    };
  }, [data]);

  return data;
};
