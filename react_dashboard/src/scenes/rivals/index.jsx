

import { Box } from "@mui/material";
import Header from "../../components/Header";
import RivalsChannel from "../../components/Rivals";

const RivalsData = () => {
    return (
        <Box mx="20px" mt="0" mb="20px">
            <Header title="Rivals channels" subtitle="Rivals data"/>
            <RivalsChannel/>

        </Box>
    )
}

export default RivalsData