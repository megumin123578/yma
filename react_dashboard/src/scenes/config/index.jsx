import { Box, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";
import CredentialsDialog from "../../components/dialogs/CredentialsDialog";

const ConfigPage = () => {
  const navigate = useNavigate();

  return (
    <Box sx={{ minHeight: "calc(100vh - 32px)", p: { xs: 0, md: 0 } }}>
      <Typography sx={{ position: "absolute", left: -9999, top: -9999 }}>
        Config
      </Typography>
      <CredentialsDialog
        open
        inline
        onClose={() => navigate("/dashboard", { replace: true })}
      />
    </Box>
  );
};

export default ConfigPage;
