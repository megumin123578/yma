import { Box } from "@mui/material";
import Header from "../../components/Header";
import ForgotPassword from "../../pages/ForgotPassword";

const Forgot = () => {
  return (
    <Box mx="20px" mt="0" mb="20px">
      <Header title="Forgot Password Page" />

      <Box
        mt={3}
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="60vh"
      >
        <ForgotPassword />
      </Box>
    </Box>
  );
};

export default Forgot;
