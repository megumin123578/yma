import { Box } from "@mui/material";
import Header from "../../components/Header";
import Smmstore from "../../components/Smmstore";

const SmmstoreScene = () => {
  return (
    <Box mx="20px" mt="0" mb="20px">
      <Header title="SMM Store" subtitle="Automatic Scheduling" />
      <Smmstore />
    </Box>
  );
};

export default SmmstoreScene;
