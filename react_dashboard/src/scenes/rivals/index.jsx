

import { Box, FormControlLabel, Stack, Switch } from "@mui/material";
import { useState } from "react";
import Header from "../../components/Header";
import RivalsChannel from "../../components/Rivals";

const RivalsData = () => {
    const [viewMode, setViewMode] = useState("list");

    return (
        <Box mx="20px" mt="0" mb="20px">
            <Stack
                direction="row"
                alignItems="center"
                justifyContent="space-between"
                flexWrap="wrap"
                gap={2}
            >
                <Header title="Rivals channels" subtitle="Rivals data"/>
                <FormControlLabel
                    control={
                        <Switch
                            checked={viewMode === "chart"}
                            onChange={(e) => setViewMode(e.target.checked ? "chart" : "list")}
                            color="warning"
                        />
                    }
                    label="Chart"
                />
            </Stack>
            <RivalsChannel viewMode={viewMode} />

        </Box>
    )
}

export default RivalsData
