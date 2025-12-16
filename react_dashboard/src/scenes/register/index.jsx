import { Box } from "@mui/material";
import Header from "../../components/Header";
import Register from "../../pages/Register";


const RegisterAccount = () => {
  return (
    <Box m="20px">
      <Header title="Register" />
    <Box mt={3}>
        <Register />
    </Box>
    </Box>
  );
};

export default RegisterAccount;



