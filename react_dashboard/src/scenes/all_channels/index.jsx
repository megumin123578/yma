import { Box } from "@mui/material";
import { useEffect, useState } from "react";
import Header from "../../components/Header";
import ContentAnalytics from "../../components/Content";

const CONTENT_LOCAL_CHANNEL_STORAGE_KEY = "content.selectedChannelId";
const CONTENT_ALL_CHANNELS_VALUE = "__all__";

const AllChannelsScene = () => {
  const [ready, setReady] = useState(typeof window === "undefined");

  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    let previousValue = null;
    try {
      previousValue = window.localStorage.getItem(CONTENT_LOCAL_CHANNEL_STORAGE_KEY);
      window.localStorage.setItem(
        CONTENT_LOCAL_CHANNEL_STORAGE_KEY,
        CONTENT_ALL_CHANNELS_VALUE
      );
    } catch {
      // ignore storage errors
    } finally {
      setReady(true);
    }

    return () => {
      try {
        if (previousValue) {
          window.localStorage.setItem(CONTENT_LOCAL_CHANNEL_STORAGE_KEY, previousValue);
        } else {
          window.localStorage.removeItem(CONTENT_LOCAL_CHANNEL_STORAGE_KEY);
        }
      } catch {
        // ignore storage errors
      }
    };
  }, []);

  return (
    <Box mx="20px" mt="0" mb="20px">
      <Header title="ALL CHANNELS" subtitle="Cross-channel content overview" />
      {ready ? (
        <Box mt={3}>
          <ContentAnalytics />
        </Box>
      ) : null}
    </Box>
  );
};

export default AllChannelsScene;
