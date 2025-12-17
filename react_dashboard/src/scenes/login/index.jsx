import { Box } from '@mui/material'
import Header from '../../components/Header'
import Login from '../../pages/Login'

const LoginPage = () => {
  return (
    <Box m="20px">
      <Header title="Youtube Manager" />
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

