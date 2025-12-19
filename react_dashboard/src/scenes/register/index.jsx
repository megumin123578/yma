import { Box } from "@mui/material";
import Header from "../../components/Header";
import Register from "../../pages/Register";


const RegisterAccount = () => {
  return (
    <Box mx="20px" mt="0" mb="20px">
      <Header title="Register Page" />
    <Box mt={3}
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="60vh">
        <Register />
    </Box>
    </Box>
  );
};

export default RegisterAccount;



