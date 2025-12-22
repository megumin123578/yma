import { Box, FormControlLabel, Stack, Switch } from "@mui/material";
import { useState } from "react";
import Header from "../../components/Header";
import SmmstoreAnalytics from "../../components/SmmstoreAnalytics";

const SmmstoreAnalyticsScene = () => {
  const [viewMode, setViewMode] = useState("orders");

  return (
    <Box mx="20px" mt="0" mb="20px">
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        flexWrap="wrap"
        gap={2}
      >
        <Header
          title="SMMStore Analytics"
          subtitle="Manage how much money spent last month"
        />
        <FormControlLabel
          control={
            <Switch
              checked={viewMode === "totals"}
              onChange={(e) =>
                setViewMode(e.target.checked ? "totals" : "orders")
              }
              color="warning"
              sx={{
                "& .MuiSwitch-track": {
                  backgroundColor: "rgba(15,23,42,0.25)",
                },
                "& .MuiSwitch-thumb": {
                  boxShadow: "0 6px 14px rgba(15,23,42,0.35)",
                },
                "&.Mui-checked .MuiSwitch-thumb": {
                  boxShadow: "0 6px 16px rgba(34,197,94,0.35)",
                },
              }}
            />
          }
          label={viewMode === "totals" ? "Totals" : "Orders"}
        />
      </Stack>
      <SmmstoreAnalytics viewMode={viewMode} />
    </Box>
  );
};

export default SmmstoreAnalyticsScene;
