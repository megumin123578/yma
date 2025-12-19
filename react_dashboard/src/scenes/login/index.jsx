import { Box } from '@mui/material'
import Header from '../../components/Header'
import Login from '../../pages/Login'

const LoginPage = () => {
  return (
    <Box mx="20px" mt="0" mb="20px">
      <Header title="Login Page" />
      <Box mt={3}
      display="flex"
      justifyContent="center"
      alignItems="center"
      minHeight="60vh">
        <Login/>
      </Box>
    </Box>
  );
};

export default LoginPage;

